import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, BusinessRuleError, ConflictError, NotFoundError
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.models.enums import UserRole
from app.repositories.doctor_repository import DoctorRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import Token, UserCreate, UserRead

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def authenticate(self, email: str, password: str) -> Token:
        user = self.users.get_by_email(email)
        # Same error for unknown user and bad password to avoid account enumeration.
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            logger.warning("Failed login attempt for %s", email)
            raise AuthenticationError("Incorrect email or password")
        token = create_access_token(user.email, user.role, {"uid": user.id})
        return Token(
            access_token=token,
            expires_in_minutes=get_settings().ACCESS_TOKEN_EXPIRE_MINUTES,
            user=UserRead.model_validate(user),
        )

    def create_user(self, payload: UserCreate) -> UserRead:
        if self.users.get_by_email(payload.email):
            raise ConflictError("A user with this email already exists")
        if payload.role == UserRole.DOCTOR and payload.doctor_id is None:
            raise BusinessRuleError("DOCTOR accounts must be linked to a doctor_id")
        if payload.doctor_id and DoctorRepository(self.db).get(payload.doctor_id) is None:
            raise NotFoundError("Doctor", payload.doctor_id)
        user = self.users.add(
            User(
                email=payload.email.lower(),
                full_name=payload.full_name,
                password_hash=hash_password(payload.password),
                role=payload.role,
                doctor_id=payload.doctor_id,
            )
        )
        self.db.commit()
        logger.info("Created user id=%s role=%s", user.id, user.role)
        return UserRead.model_validate(user)

    def list_users(self) -> list[UserRead]:
        return [UserRead.model_validate(u) for u in self.users.list_all()]

    def ensure_user(self, email: str, password: str, full_name: str, role: UserRole, doctor_id: int | None = None) -> bool:
        """Idempotently create a user (used by the seed script). Returns True if created."""
        if self.users.get_by_email(email):
            return False
        self.users.add(
            User(email=email.lower(), full_name=full_name, password_hash=hash_password(password), role=role, doctor_id=doctor_id)
        )
        self.db.commit()
        return True
