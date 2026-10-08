from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import Gender
from app.schemas.common import ORMModel

PHONE_PATTERN = r"^\+?[0-9\-\s()]{7,20}$"


class PatientBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    date_of_birth: date
    gender: Gender = Gender.UNDISCLOSED
    phone: str | None = Field(None, pattern=PHONE_PATTERN)
    email: EmailStr | None = None

    @field_validator("date_of_birth")
    @classmethod
    def _dob_valid(cls, value: date) -> date:
        today = date.today()
        if value > today:
            raise ValueError("date_of_birth cannot be in the future")
        if today.year - value.year > 120:
            raise ValueError("date_of_birth is not plausible")
        return value


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    date_of_birth: date | None = None
    gender: Gender | None = None
    phone: str | None = Field(None, pattern=PHONE_PATTERN)
    email: EmailStr | None = None

    @field_validator("date_of_birth")
    @classmethod
    def _dob_valid(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return value


class PatientRead(ORMModel):
    id: int
    name: str
    date_of_birth: date
    gender: str
    phone: str | None
    email: str | None
    created_at: datetime
    updated_at: datetime


class PatientStats(BaseModel):
    total_appointments: int
    completed: int
    no_shows: int
    cancellations: int
    upcoming: int


class PatientDetail(PatientRead):
    stats: PatientStats
