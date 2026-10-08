from collections.abc import Sequence

from sqlalchemy import func, select

from app.models import Department, Doctor
from app.repositories.base import BaseRepository


class DepartmentRepository(BaseRepository[Department]):
    model = Department

    def get_by_name(self, name: str) -> Department | None:
        return self.db.scalar(select(Department).where(func.lower(Department.name) == name.lower()))

    def list_with_doctor_counts(self) -> Sequence[tuple[Department, int]]:
        stmt = (
            select(Department, func.count(Doctor.id))
            .outerjoin(Doctor, Doctor.department_id == Department.id)
            .group_by(Department.id)
            .order_by(Department.name)
        )
        return [(row[0], row[1]) for row in self.db.execute(stmt).all()]

    def doctor_count(self, department_id: int) -> int:
        return self.db.scalar(select(func.count(Doctor.id)).where(Doctor.department_id == department_id)) or 0

    def list_all(self) -> Sequence[Department]:
        return self.db.scalars(select(Department).order_by(Department.name)).all()
