"""Generic repository with the CRUD primitives shared by all entities."""

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, entity_id: int) -> ModelT | None:
        return self.db.get(self.model, entity_id)

    def add(self, entity: ModelT) -> ModelT:
        self.db.add(entity)
        self.db.flush()
        return entity

    def delete(self, entity: ModelT) -> None:
        self.db.delete(entity)
        self.db.flush()

    def update(self, entity: ModelT, values: dict[str, Any]) -> ModelT:
        for key, value in values.items():
            setattr(entity, key, value)
        self.db.flush()
        return entity

    def paginate(self, stmt: Select[Any], limit: int, offset: int) -> tuple[Sequence[Any], int]:
        total = self.db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        rows = self.db.execute(stmt.limit(limit).offset(offset)).unique().scalars().all()
        return rows, total
