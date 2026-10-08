from datetime import date, datetime, time

from pydantic import BaseModel, Field, model_validator

from app.models.enums import AppointmentStatus
from app.schemas.common import ORMModel


class AppointmentCreate(BaseModel):
    patient_id: int = Field(..., gt=0)
    doctor_id: int = Field(..., gt=0)
    appointment_date: date
    appointment_time: time
    booking_date: date | None = Field(None, description="Defaults to today")

    @model_validator(mode="after")
    def _check_dates(self) -> "AppointmentCreate":
        booking = self.booking_date or date.today()
        if self.appointment_date < booking:
            raise ValueError("appointment_date cannot be before booking_date")
        return self


class AppointmentUpdate(BaseModel):
    """Reschedule / reassign. Status changes go through the dedicated status endpoint."""

    doctor_id: int | None = Field(None, gt=0)
    appointment_date: date | None = None
    appointment_time: time | None = None


class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus
    notes: str | None = Field(None, max_length=2000)


class StatusHistoryRead(ORMModel):
    id: int
    old_status: str | None
    new_status: str
    changed_at: datetime
    changed_by: str


class LatestPrediction(BaseModel):
    no_show_probability: float
    risk_level: str
    created_at: datetime


class AppointmentRead(ORMModel):
    id: int
    patient_id: int
    patient_name: str | None = None
    doctor_id: int
    doctor_name: str | None = None
    department_id: int
    department_name: str | None = None
    appointment_date: date
    appointment_time: time
    booking_date: date
    status: str
    created_at: datetime
    updated_at: datetime
    latest_prediction: LatestPrediction | None = None


class AppointmentDetail(AppointmentRead):
    status_history: list[StatusHistoryRead] = []
