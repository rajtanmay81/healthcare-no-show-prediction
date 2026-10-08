"""Aggregate SQL queries for analytics. All numbers the assistant reports originate here."""

from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import ColumnElement, Date, Row, Select, and_, case, cast, extract, func, select, true
from sqlalchemy.orm import Session

from app.models import Appointment, AppointmentPrediction, Department, Doctor, Patient
from app.models.enums import AppointmentStatus, RiskLevel, UPCOMING_STATUSES

S = AppointmentStatus


def _count_status(status: AppointmentStatus) -> ColumnElement[int]:
    return func.count(case((Appointment.status == status, 1)))


STATUS_COLUMNS = (
    func.count(Appointment.id).label("total"),
    _count_status(S.SCHEDULED).label("scheduled"),
    _count_status(S.CONFIRMED).label("confirmed"),
    _count_status(S.COMPLETED).label("completed"),
    _count_status(S.CANCELLED).label("cancelled"),
    _count_status(S.NO_SHOW).label("no_show"),
)


def latest_prediction_subquery() -> Any:
    """Most recent prediction per appointment (PostgreSQL DISTINCT ON)."""
    return (
        select(
            AppointmentPrediction.appointment_id,
            AppointmentPrediction.no_show_probability,
            AppointmentPrediction.risk_level,
            AppointmentPrediction.factors,
        )
        .distinct(AppointmentPrediction.appointment_id)
        .order_by(
            AppointmentPrediction.appointment_id,
            AppointmentPrediction.created_at.desc(),
            AppointmentPrediction.id.desc(),
        )
        .subquery("latest_prediction")
    )


class AnalyticsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _filtered(stmt: Select[Any], date_from: date | None, date_to: date | None, department_id: int | None) -> Select[Any]:
        if date_from:
            stmt = stmt.where(Appointment.appointment_date >= date_from)
        if date_to:
            stmt = stmt.where(Appointment.appointment_date <= date_to)
        if department_id:
            stmt = stmt.where(Appointment.department_id == department_id)
        return stmt

    def status_counts(self, date_from: date | None, date_to: date | None, department_id: int | None) -> Row[Any]:
        stmt = self._filtered(select(*STATUS_COLUMNS), date_from, date_to, department_id)
        return self.db.execute(stmt).one()

    def upcoming_counts(self, today: date, until: date | None, department_id: int | None) -> tuple[int, int]:
        latest = latest_prediction_subquery()
        stmt = (
            select(
                func.count(Appointment.id),
                func.count(case((latest.c.risk_level == RiskLevel.HIGH, 1))),
            )
            .select_from(Appointment)
            .outerjoin(latest, latest.c.appointment_id == Appointment.id)
            .where(Appointment.status.in_(list(UPCOMING_STATUSES)), Appointment.appointment_date >= today)
        )
        if until:
            stmt = stmt.where(Appointment.appointment_date <= until)
        if department_id:
            stmt = stmt.where(Appointment.department_id == department_id)
        total, high = self.db.execute(stmt).one()
        return int(total), int(high)

    def by_department(self, date_from: date | None, date_to: date | None, today: date) -> Sequence[Row[Any]]:
        latest = latest_prediction_subquery()
        is_upcoming = and_(Appointment.status.in_(list(UPCOMING_STATUSES)), Appointment.appointment_date >= today)
        in_period = and_(
            Appointment.appointment_date >= date_from if date_from else true(),
            Appointment.appointment_date <= date_to if date_to else true(),
        )

        def period_count(status: AppointmentStatus) -> ColumnElement[int]:
            return func.count(case((and_(in_period, Appointment.status == status), 1)))

        stmt = (
            select(
                Department.id,
                Department.name,
                func.count(case((in_period, Appointment.id))).label("total"),
                period_count(S.COMPLETED).label("completed"),
                period_count(S.NO_SHOW).label("no_show"),
                period_count(S.CANCELLED).label("cancelled"),
                func.avg(case((in_period, Appointment.appointment_date - Appointment.booking_date))).label("avg_lead"),
                func.count(case((is_upcoming, 1))).label("upcoming"),
                func.count(case((and_(is_upcoming, latest.c.risk_level == RiskLevel.HIGH), 1))).label("high_risk"),
                func.avg(case((is_upcoming, latest.c.no_show_probability))).label("avg_risk"),
            )
            .select_from(Department)
            .outerjoin(Appointment, Appointment.department_id == Department.id)
            .outerjoin(latest, latest.c.appointment_id == Appointment.id)
            .group_by(Department.id, Department.name)
            .order_by(Department.name)
        )
        return self.db.execute(stmt).all()

    def trends(
        self, granularity: str, date_from: date | None, date_to: date | None, department_id: int | None
    ) -> Sequence[Row[Any]]:
        bucket = cast(func.date_trunc(granularity, Appointment.appointment_date), Date).label("bucket")
        stmt = select(
            bucket,
            func.count(Appointment.id).label("total"),
            _count_status(S.COMPLETED).label("completed"),
            _count_status(S.NO_SHOW).label("no_show"),
            _count_status(S.CANCELLED).label("cancelled"),
        )
        stmt = self._filtered(stmt, date_from, date_to, department_id).group_by(bucket).order_by(bucket)
        return self.db.execute(stmt).all()

    def by_day_of_week(self, date_from: date | None, date_to: date | None, department_id: int | None) -> Sequence[Row[Any]]:
        dow = extract("isodow", Appointment.appointment_date).label("dow")
        stmt = select(
            dow,
            func.count(case((Appointment.status.in_([S.COMPLETED, S.NO_SHOW]), 1))).label("outcomes"),
            _count_status(S.NO_SHOW).label("no_show"),
        )
        stmt = self._filtered(stmt, date_from, date_to, department_id).group_by(dow).order_by(dow)
        return self.db.execute(stmt).all()

    def upcoming_with_predictions(self, today: date, until: date, department_id: int | None) -> Sequence[Row[Any]]:
        latest = latest_prediction_subquery()
        stmt = (
            select(Appointment.id, latest.c.no_show_probability, latest.c.risk_level)
            .select_from(Appointment)
            .outerjoin(latest, latest.c.appointment_id == Appointment.id)
            .where(
                Appointment.status.in_(list(UPCOMING_STATUSES)),
                Appointment.appointment_date.between(today, until),
            )
        )
        if department_id:
            stmt = stmt.where(Appointment.department_id == department_id)
        return self.db.execute(stmt).all()

    def high_risk_upcoming(
        self, today: date, until: date, min_probability: float, department_id: int | None, limit: int
    ) -> Sequence[Row[Any]]:
        latest = latest_prediction_subquery()
        stmt = (
            select(
                Appointment.id,
                Appointment.patient_id,
                Patient.name.label("patient_name"),
                Department.name.label("department_name"),
                Doctor.name.label("doctor_name"),
                Appointment.appointment_date,
                Appointment.appointment_time,
                Appointment.status,
                latest.c.no_show_probability,
                latest.c.risk_level,
                latest.c.factors,
            )
            .join(latest, latest.c.appointment_id == Appointment.id)
            .join(Patient, Patient.id == Appointment.patient_id)
            .join(Department, Department.id == Appointment.department_id)
            .join(Doctor, Doctor.id == Appointment.doctor_id)
            .where(
                Appointment.status.in_(list(UPCOMING_STATUSES)),
                Appointment.appointment_date.between(today, until),
                latest.c.no_show_probability >= min_probability,
            )
            .order_by(latest.c.no_show_probability.desc())
            .limit(limit)
        )
        if department_id:
            stmt = stmt.where(Appointment.department_id == department_id)
        return self.db.execute(stmt).all()
