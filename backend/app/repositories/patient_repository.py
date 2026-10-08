from collections.abc import Sequence

from sqlalchemy import case, func, or_, select

from app.models import Appointment, Patient
from app.models.enums import AppointmentStatus, UPCOMING_STATUSES
from app.repositories.base import BaseRepository


class PatientRepository(BaseRepository[Patient]):
    model = Patient

    def get_by_email(self, email: str) -> Patient | None:
        return self.db.scalar(select(Patient).where(func.lower(Patient.email) == email.lower()))

    def list(self, search: str | None, limit: int, offset: int) -> tuple[Sequence[Patient], int]:
        stmt = select(Patient).order_by(Patient.id.desc())
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(or_(Patient.name.ilike(pattern), Patient.email.ilike(pattern), Patient.phone.ilike(pattern)))
        return self.paginate(stmt, limit, offset)

    def appointment_stats(self, patient_id: int) -> dict[str, int]:
        status = Appointment.status
        stmt = select(
            func.count(Appointment.id),
            func.count(case((status == AppointmentStatus.COMPLETED, 1))),
            func.count(case((status == AppointmentStatus.NO_SHOW, 1))),
            func.count(case((status == AppointmentStatus.CANCELLED, 1))),
            func.count(case((status.in_(list(UPCOMING_STATUSES)), 1))),
        ).where(Appointment.patient_id == patient_id)
        total, completed, no_shows, cancellations, upcoming = self.db.execute(stmt).one()
        return {
            "total_appointments": total,
            "completed": completed,
            "no_shows": no_shows,
            "cancellations": cancellations,
            "upcoming": upcoming,
        }

    def has_appointments(self, patient_id: int) -> bool:
        return self.db.scalar(select(func.count(Appointment.id)).where(Appointment.patient_id == patient_id)) > 0
