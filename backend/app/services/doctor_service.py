import logging
from datetime import date, time

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import Doctor
from app.repositories.department_repository import DepartmentRepository
from app.repositories.doctor_repository import DoctorRepository
from app.schemas.common import Page
from app.schemas.doctor import DoctorCreate, DoctorRead, DoctorSchedule, ScheduleSlot

logger = logging.getLogger(__name__)

# Clinic working hours: 30-minute slots from 09:00 to 16:30.
SLOT_TIMES: tuple[time, ...] = tuple(time(h, m) for h in range(9, 17) for m in (0, 30))


def to_doctor_read(doctor: Doctor) -> DoctorRead:
    return DoctorRead.model_validate(doctor).model_copy(
        update={"department_name": doctor.department.name if doctor.department else None}
    )


class DoctorService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = DoctorRepository(db)
        self.departments = DepartmentRepository(db)

    def create(self, payload: DoctorCreate) -> DoctorRead:
        if self.departments.get(payload.department_id) is None:
            raise NotFoundError("Department", payload.department_id)
        if self.repo.get_by_email(payload.email):
            raise ConflictError(f"A doctor with email {payload.email} already exists")
        doctor = self.repo.add(Doctor(**payload.model_dump()))
        self.db.commit()
        logger.info("Created doctor id=%s department_id=%s", doctor.id, doctor.department_id)
        return to_doctor_read(self.repo.get_with_department(doctor.id))  # type: ignore[arg-type]

    def list(self, department_id: int | None, search: str | None, limit: int, offset: int) -> Page[DoctorRead]:
        rows, total = self.repo.list(department_id, search, limit, offset)
        return Page(items=[to_doctor_read(d) for d in rows], total=total, limit=limit, offset=offset)

    def get(self, doctor_id: int) -> DoctorRead:
        doctor = self.repo.get_with_department(doctor_id)
        if doctor is None:
            raise NotFoundError("Doctor", doctor_id)
        return to_doctor_read(doctor)

    def schedule(self, doctor_id: int, day: date) -> DoctorSchedule:
        if self.repo.get(doctor_id) is None:
            raise NotFoundError("Doctor", doctor_id)
        booked = {a.appointment_time: a.id for a in self.repo.booked_slots(doctor_id, day)}
        slots = [ScheduleSlot(time=t, available=t not in booked, appointment_id=booked.get(t)) for t in SLOT_TIMES]
        return DoctorSchedule(doctor_id=doctor_id, date=day, slots=slots)
