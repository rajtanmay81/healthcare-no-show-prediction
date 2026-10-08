from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.core.dependencies import AdminOnly, AdminOrStaff, AnyRole, DbSession
from app.schemas.common import Page
from app.schemas.patient import PatientCreate, PatientDetail, PatientRead, PatientUpdate
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient(payload: PatientCreate, db: DbSession, _: AdminOrStaff) -> PatientRead:
    return PatientService(db).create(payload)


@router.get("", response_model=Page[PatientRead])
def list_patients(
    db: DbSession,
    user: AnyRole,
    search: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[PatientRead]:
    return PatientService(db).list(search, limit, offset, user)


@router.get("/{patient_id}", response_model=PatientDetail)
def get_patient(patient_id: int, db: DbSession, user: AnyRole) -> PatientDetail:
    return PatientService(db).get(patient_id, user)


@router.put("/{patient_id}", response_model=PatientRead)
def update_patient(patient_id: int, payload: PatientUpdate, db: DbSession, _: AdminOrStaff) -> PatientRead:
    return PatientService(db).update(patient_id, payload)


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(patient_id: int, db: DbSession, _: AdminOnly) -> Response:
    PatientService(db).delete(patient_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
