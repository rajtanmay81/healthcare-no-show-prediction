from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.dependencies import AdminOnly, CurrentUser, DbSession
from app.schemas.auth import Token, UserCreate, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token, summary="Obtain a JWT access token")
def login(db: DbSession, form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    """OAuth2 password flow: send `username` (email) and `password` as form fields."""
    return AuthService(db).authenticate(form.username, form.password)


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DbSession, _: AdminOnly) -> UserRead:
    return AuthService(db).create_user(payload)


@router.get("/users", response_model=list[UserRead])
def list_users(db: DbSession, _: AdminOnly) -> list[UserRead]:
    return AuthService(db).list_users()
