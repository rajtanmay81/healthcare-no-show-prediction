from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models import Appointment, Doctor
from app.models.enums import AppointmentStatus
from app.repositories.base import BaseRepository


class DoctorRepository(BaseRepository[Doctor]):
    model = Doctor

    def get_with_department(self, doctor_id: int) -> Doctor | None:
        return self.db.scalar(select(Doctor).options(joinedload(Doctor.department)).where(Doctor.id == doctor_id))

    def get_by_email(self, email: str) -> Doctor | None:
        return self.db.scalar(select(Doctor).where(Doctor.email == email))

    def list(
        self, department_id: int | None, search: str | None, limit: int, offset: int
    ) -> tuple[Sequence[Doctor], int]:
        stmt = select(Doctor).options(joinedload(Doctor.department)).order_by(Doctor.name)
        if department_id:
            stmt = stmt.where(Doctor.department_id == department_id)
        if search:
            stmt = stmt.where(Doctor.name.ilike(f"%{search}%"))
        return self.paginate(stmt, limit, offset)

    def booked_slots(self, doctor_id: int, day: date) -> Sequence[Appointment]:
        stmt = select(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == day,
            Appointment.status != AppointmentStatus.CANCELLED,
        )
        return self.db.scalars(stmt).all()
