from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.dependencies import AdminOnly, AnyRole, DbSession
from app.schemas.common import Page
from app.schemas.doctor import DoctorCreate, DoctorRead, DoctorSchedule
from app.services.doctor_service import DoctorService

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.post("", response_model=DoctorRead, status_code=status.HTTP_201_CREATED)
def create_doctor(payload: DoctorCreate, db: DbSession, _: AdminOnly) -> DoctorRead:
    return DoctorService(db).create(payload)


@router.get("", response_model=Page[DoctorRead])
def list_doctors(
    db: DbSession,
    _: AnyRole,
    department_id: int | None = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[DoctorRead]:
    return DoctorService(db).list(department_id, search, limit, offset)


@router.get("/{doctor_id}", response_model=DoctorRead)
def get_doctor(doctor_id: int, db: DbSession, _: AnyRole) -> DoctorRead:
    return DoctorService(db).get(doctor_id)


@router.get("/{doctor_id}/schedule", response_model=DoctorSchedule, summary="Booked and free slots for a day")
def get_schedule(doctor_id: int, db: DbSession, _: AnyRole, day: Annotated[date, Query(alias="date")]) -> DoctorSchedule:
    return DoctorService(db).schedule(doctor_id, day)
