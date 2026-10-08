"""FastAPI dependencies: DB session, authenticated user and role guards."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.db.database import get_db
from app.models import User
from app.models.enums import UserRole
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DbSession, token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    payload = decode_access_token(token)
    user = UserRepository(db).get_by_email(payload["sub"])
    if user is None or not user.is_active:
        raise AuthenticationError("User is inactive or no longer exists")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    allowed = {r.value for r in roles}

    def _guard(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise PermissionDeniedError(f"This action requires one of the roles: {', '.join(sorted(allowed))}")
        return user

    return _guard


# Common role groups
AdminOnly = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
AdminOrStaff = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.STAFF))]
AnyRole = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.STAFF, UserRole.DOCTOR))]
