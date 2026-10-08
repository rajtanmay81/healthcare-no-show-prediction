from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.dependencies import AdminOrStaff, AnyRole, DbSession
from app.models.enums import AppointmentStatus
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentDetail,
    AppointmentRead,
    AppointmentStatusUpdate,
    AppointmentUpdate,
)
from app.schemas.common import Page
from app.services.appointment_service import AppointmentService

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.post("", response_model=AppointmentDetail, status_code=status.HTTP_201_CREATED)
def book_appointment(payload: AppointmentCreate, db: DbSession, user: AdminOrStaff) -> AppointmentDetail:
    """Book an appointment. The no-show model scores it automatically (best effort)."""
    return AppointmentService(db).create(payload, user)


@router.get("", response_model=Page[AppointmentRead])
def list_appointments(
    db: DbSession,
    user: AnyRole,
    status_filter: Annotated[AppointmentStatus | None, Query(alias="status")] = None,
    department_id: int | None = None,
    doctor_id: int | None = None,
    patient_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: Annotated[str | None, Query(max_length=100, description="Patient name")] = None,
    sort: Annotated[str, Query(pattern="^(newest|oldest)$")] = "newest",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AppointmentRead]:
    return AppointmentService(db).list(
        user,
        status=status_filter,
        department_id=department_id,
        doctor_id=doctor_id,
        patient_id=patient_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        limit=limit,
        offset=offset,
        newest_first=sort == "newest",
    )


@router.get("/{appointment_id}", response_model=AppointmentDetail)
def get_appointment(appointment_id: int, db: DbSession, user: AnyRole) -> AppointmentDetail:
    return AppointmentService(db).get(appointment_id, user)


@router.patch("/{appointment_id}", response_model=AppointmentDetail, summary="Reschedule or reassign")
def update_appointment(
    appointment_id: int, payload: AppointmentUpdate, db: DbSession, user: AdminOrStaff
) -> AppointmentDetail:
    return AppointmentService(db).update(appointment_id, payload, user)


@router.patch("/{appointment_id}/status", response_model=AppointmentDetail, summary="Change status (audited)")
def change_status(
    appointment_id: int, payload: AppointmentStatusUpdate, db: DbSession, user: AnyRole
) -> AppointmentDetail:
    return AppointmentService(db).change_status(appointment_id, payload, user)
