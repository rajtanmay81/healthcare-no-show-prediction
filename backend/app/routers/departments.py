from fastapi import APIRouter, status

from app.core.dependencies import AdminOnly, AnyRole, DbSession
from app.schemas.department import DepartmentCreate, DepartmentRead
from app.services.department_service import DepartmentService

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.post("", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentCreate, db: DbSession, _: AdminOnly) -> DepartmentRead:
    return DepartmentService(db).create(payload)


@router.get("", response_model=list[DepartmentRead])
def list_departments(db: DbSession, _: AnyRole) -> list[DepartmentRead]:
    return DepartmentService(db).list()


@router.get("/{department_id}", response_model=DepartmentRead)
def get_department(department_id: int, db: DbSession, _: AnyRole) -> DepartmentRead:
    return DepartmentService(db).get(department_id)
