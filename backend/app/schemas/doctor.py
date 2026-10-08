from datetime import date, datetime, time

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class DoctorCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    department_id: int = Field(..., gt=0)
    specialization: str | None = Field(None, max_length=120)
    email: EmailStr
    phone: str | None = Field(None, pattern=r"^\+?[0-9\-\s()]{7,20}$")


class DoctorRead(ORMModel):
    id: int
    name: str
    department_id: int
    department_name: str | None = None
    specialization: str | None
    email: str
    phone: str | None
    created_at: datetime


class ScheduleSlot(BaseModel):
    time: time
    available: bool
    appointment_id: int | None = None


class DoctorSchedule(BaseModel):
    doctor_id: int
    date: date
    slots: list[ScheduleSlot]
