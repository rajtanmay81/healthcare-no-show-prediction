from collections.abc import Sequence
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.models import Appointment, AppointmentStatusHistory, Patient, VisitHistory
from app.models.enums import AppointmentStatus
from app.repositories.base import BaseRepository

_EAGER = (joinedload(Appointment.patient), joinedload(Appointment.doctor), joinedload(Appointment.department))


class AppointmentRepository(BaseRepository[Appointment]):
    model = Appointment

    def get_detailed(self, appointment_id: int) -> Appointment | None:
        stmt = (
            select(Appointment)
            .options(*_EAGER, selectinload(Appointment.status_history), selectinload(Appointment.predictions))
            .where(Appointment.id == appointment_id)
        )
        return self.db.scalar(stmt)

    def list(
        self,
        *,
        status: AppointmentStatus | None,
        department_id: int | None,
        doctor_id: int | None,
        patient_id: int | None,
        date_from: date | None,
        date_to: date | None,
        search: str | None,
        limit: int,
        offset: int,
        newest_first: bool = True,
    ) -> tuple[Sequence[Appointment], int]:
        stmt = select(Appointment).options(*_EAGER, selectinload(Appointment.predictions))
        if status:
            stmt = stmt.where(Appointment.status == status)
        if department_id:
            stmt = stmt.where(Appointment.department_id == department_id)
        if doctor_id:
            stmt = stmt.where(Appointment.doctor_id == doctor_id)
        if patient_id:
            stmt = stmt.where(Appointment.patient_id == patient_id)
        if date_from:
            stmt = stmt.where(Appointment.appointment_date >= date_from)
        if date_to:
            stmt = stmt.where(Appointment.appointment_date <= date_to)
        if search:
            stmt = stmt.join(Patient, Patient.id == Appointment.patient_id).where(Patient.name.ilike(f"%{search}%"))
        order = (Appointment.appointment_date.desc(), Appointment.appointment_time.desc()) if newest_first else (
            Appointment.appointment_date.asc(),
            Appointment.appointment_time.asc(),
        )
        return self.paginate(stmt.order_by(*order, Appointment.id), limit, offset)

    def find_slot_conflict(
        self, doctor_id: int, day: date, slot: time, exclude_id: int | None = None
    ) -> Appointment | None:
        stmt = select(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == day,
            Appointment.appointment_time == slot,
            Appointment.status != AppointmentStatus.CANCELLED,
        )
        if exclude_id:
            stmt = stmt.where(Appointment.id != exclude_id)
        return self.db.scalar(stmt.limit(1))

    def patient_appointments(self, patient_ids: Sequence[int]) -> Sequence[Appointment]:
        """All appointments for the given patients (used to build historical ML features)."""
        stmt = (
            select(Appointment)
            .options(joinedload(Appointment.patient), joinedload(Appointment.department))
            .where(Appointment.patient_id.in_(list(patient_ids)))
        )
        return self.db.scalars(stmt).all()

    def upcoming(self, from_day: date, to_day: date) -> Sequence[Appointment]:
        stmt = select(Appointment).where(
            Appointment.appointment_date.between(from_day, to_day),
            Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
        )
        return self.db.scalars(stmt).all()

    def add_status_history(self, entry: AppointmentStatusHistory) -> AppointmentStatusHistory:
        self.db.add(entry)
        self.db.flush()
        return entry

    def add_visit(self, visit: VisitHistory) -> VisitHistory:
        self.db.add(visit)
        self.db.flush()
        return visit
