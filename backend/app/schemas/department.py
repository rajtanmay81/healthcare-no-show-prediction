from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: str | None = Field(None, max_length=2000)


class DepartmentRead(ORMModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    doctor_count: int = 0
