import logging

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models import Department
from app.repositories.department_repository import DepartmentRepository
from app.schemas.department import DepartmentCreate, DepartmentRead

logger = logging.getLogger(__name__)


class DepartmentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = DepartmentRepository(db)

    def create(self, payload: DepartmentCreate) -> DepartmentRead:
        name = payload.name.strip()
        if self.repo.get_by_name(name):
            raise ConflictError(f"Department '{name}' already exists")
        department = self.repo.add(Department(name=name, description=payload.description))
        self.db.commit()
        logger.info("Created department id=%s name=%s", department.id, department.name)
        return DepartmentRead.model_validate(department)

    def list(self) -> list[DepartmentRead]:
        return [
            DepartmentRead.model_validate(dept).model_copy(update={"doctor_count": count})
            for dept, count in self.repo.list_with_doctor_counts()
        ]

    def get(self, department_id: int) -> DepartmentRead:
        department = self.repo.get(department_id)
        if department is None:
            raise NotFoundError("Department", department_id)
        return DepartmentRead.model_validate(department).model_copy(
            update={"doctor_count": self.repo.doctor_count(department_id)}
        )
