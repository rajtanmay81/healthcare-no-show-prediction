"""Load raw appointment data from the synthetic CSV or from the live PostgreSQL database."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.preprocessing import RAW_COLUMNS


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found at {path}. Run `python -m app.ml.generate_data` first.")
    return pd.read_csv(path)[RAW_COLUMNS]


def load_from_database(db: Session) -> pd.DataFrame:
    """Export every appointment (all statuses) so history features include cancellations."""
    from app.models import Appointment, Department, Patient

    stmt = (
        select(
            Appointment.id.label("appointment_id"),
            Appointment.patient_id,
            Patient.date_of_birth,
            Department.name.label("department"),
            Appointment.appointment_date,
            Appointment.appointment_time,
            Appointment.booking_date,
            Appointment.status,
        )
        .join(Patient, Patient.id == Appointment.patient_id)
        .join(Department, Department.id == Appointment.department_id)
    )
    rows = db.execute(stmt).mappings().all()
    frame = pd.DataFrame(rows, columns=RAW_COLUMNS)
    if not frame.empty:
        frame["appointment_time"] = frame["appointment_time"].map(lambda t: t.strftime("%H:%M"))
    return frame
