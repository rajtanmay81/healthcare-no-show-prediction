"""Load the SYNTHETIC dataset into PostgreSQL and bootstrap user accounts.

Idempotent: if patients already exist, data loading is skipped (use ``--reset`` to wipe and reload).

Usage:
    python -m app.scripts.seed            # load if empty, create admin/demo users, score upcoming appointments
    python -m app.scripts.seed --reset    # truncate all domain tables first (user accounts are re-created)
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime, time, timedelta

import pandas as pd
from sqlalchemy import func, insert, select, text

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.database import SessionLocal
from app.ml.predict import get_predictor
from app.models import (
    Appointment,
    AppointmentStatusHistory,
    Department,
    Doctor,
    Patient,
    VisitHistory,
)
from app.models.enums import UserRole
from app.scripts.create_admin import ensure_admin
from app.services.auth_service import AuthService
from app.services.prediction_service import PredictionService

logger = logging.getLogger(__name__)
SEED_ACTOR = "system:synthetic-seed"
DOMAIN_TABLES = (
    "appointment_predictions, appointment_status_history, visit_history, appointments, doctors, departments, patients"
)


def _ts(day: object, at: time) -> datetime:
    return datetime.combine(pd.Timestamp(day).date(), at, tzinfo=UTC)


def load_dataset(reset: bool) -> None:
    settings = get_settings()
    data_dir = settings.DATA_DIR
    with SessionLocal() as db:
        if reset:
            db.execute(text(f"TRUNCATE {DOMAIN_TABLES} RESTART IDENTITY CASCADE"))
            db.commit()
            logger.info("Domain tables truncated")
        if db.scalar(select(func.count(Patient.id))):
            logger.info("Database already contains patients - skipping data load")
            return

        departments = pd.read_csv(data_dir / "departments.csv")
        doctors = pd.read_csv(data_dir / "doctors.csv")
        patients = pd.read_csv(data_dir / "patients.csv", parse_dates=["date_of_birth"])
        appts = pd.read_csv(data_dir / "appointments.csv", parse_dates=["appointment_date", "booking_date"])

        dept_ids = {}
        for row in departments.itertuples(index=False):
            dept = Department(name=row.department, description=row.description)
            db.add(dept)
            db.flush()
            dept_ids[row.department] = dept.id

        db.execute(
            insert(Doctor),
            [
                {
                    "id": int(r.doctor_id),
                    "name": r.doctor_name,
                    "department_id": dept_ids[r.department],
                    "specialization": r.specialization,
                    "email": r.email,
                    "phone": r.phone,
                }
                for r in doctors.itertuples(index=False)
            ],
        )
        db.execute(
            insert(Patient),
            [
                {
                    "id": int(r.patient_id),
                    "name": r.name,
                    "date_of_birth": r.date_of_birth.date(),
                    "gender": r.gender,
                    "phone": r.phone,
                    "email": r.email,
                }
                for r in patients.itertuples(index=False)
            ],
        )

        appt_rows, history_rows, visit_rows = [], [], []
        for r in appts.itertuples(index=False):
            appt_id = int(r.appointment_id)
            appt_day = r.appointment_date.date()
            slot = datetime.strptime(r.appointment_time, "%H:%M").time()
            booked_at = _ts(r.booking_date, time(8, 30))
            appt_rows.append(
                {
                    "id": appt_id,
                    "patient_id": int(r.patient_id),
                    "doctor_id": int(r.doctor_id),
                    "department_id": dept_ids[r.department],
                    "appointment_date": appt_day,
                    "appointment_time": slot,
                    "booking_date": r.booking_date.date(),
                    "status": r.status,
                    "created_at": booked_at,
                    "updated_at": booked_at,
                }
            )
            history_rows.append(
                {"appointment_id": appt_id, "old_status": None, "new_status": "scheduled", "changed_at": booked_at, "changed_by": SEED_ACTOR}
            )
            if r.status != "scheduled":
                changed = (
                    _ts(appt_day, slot) + timedelta(hours=1)
                    if r.status in ("completed", "no_show")
                    else booked_at + (r.appointment_date - r.booking_date) / 2
                )
                history_rows.append(
                    {"appointment_id": appt_id, "old_status": "scheduled", "new_status": r.status, "changed_at": changed, "changed_by": SEED_ACTOR}
                )
            if r.status in ("completed", "no_show"):
                visit_rows.append(
                    {
                        "patient_id": int(r.patient_id),
                        "appointment_id": appt_id,
                        "visit_date": appt_day,
                        "visit_status": "attended" if r.status == "completed" else "missed",
                    }
                )

        db.execute(insert(Appointment), appt_rows)
        db.execute(insert(AppointmentStatusHistory), history_rows)
        db.execute(insert(VisitHistory), visit_rows)
        # Explicit ids were inserted -> move sequences past them.
        for table in ("patients", "doctors", "appointments"):
            db.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), (SELECT MAX(id) FROM {table}))"))
        db.commit()
        logger.info(
            "Loaded SYNTHETIC data: %d departments, %d doctors, %d patients, %d appointments, %d visits",
            len(dept_ids),
            len(doctors),
            len(patients),
            len(appt_rows),
            len(visit_rows),
        )


def ensure_demo_users() -> None:
    password = get_settings().DEMO_USERS_PASSWORD
    if not password:
        logger.info("DEMO_USERS_PASSWORD not set - skipping demo STAFF/DOCTOR accounts")
        return
    with SessionLocal() as db:
        first_doctor = db.scalar(select(Doctor).order_by(Doctor.id).limit(1))
        service = AuthService(db)
        service.ensure_user("staff@citygeneral.org", password, "Front Desk Staff", UserRole.STAFF)
        if first_doctor:
            service.ensure_user("doctor@citygeneral.org", password, first_doctor.name, UserRole.DOCTOR, first_doctor.id)
    logger.info("Demo accounts ensured (staff@citygeneral.org, doctor@citygeneral.org)")


def score_upcoming(days_ahead: int = 30) -> None:
    if not get_predictor().is_loaded:
        logger.warning("No trained model - skipping scoring of upcoming appointments")
        return
    with SessionLocal() as db:
        result = PredictionService(db).predict_upcoming(days_ahead)
    logger.info("Scored %d upcoming appointments: %s", result.scored, result.risk_counts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the database with SYNTHETIC data")
    parser.add_argument(
        "--reset", action="store_true", help="Truncate domain tables (and, via FK cascade, user accounts) before loading"
    )
    parser.add_argument("--skip-scoring", action="store_true")
    args = parser.parse_args()
    configure_logging(get_settings().LOG_LEVEL)

    load_dataset(args.reset)
    # Accounts are ensured *after* loading: --reset cascades to `users` (users.doctor_id -> doctors).
    ensure_admin()
    ensure_demo_users()
    if not args.skip_scoring:
        score_upcoming()


if __name__ == "__main__":
    main()
