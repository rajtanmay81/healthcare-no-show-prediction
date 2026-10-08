from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole
from app.schemas.common import ORMModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: "UserRead"


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=120)
    password: str = Field(..., min_length=10, max_length=128)
    role: UserRole
    doctor_id: int | None = Field(None, gt=0)


class UserRead(ORMModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    doctor_id: int | None


Token.model_rebuild()
