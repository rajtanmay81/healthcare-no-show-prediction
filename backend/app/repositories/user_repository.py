from collections.abc import Sequence

from sqlalchemy import func, select

from app.models import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(func.lower(User.email) == email.lower()))

    def list_all(self) -> Sequence[User]:
        return self.db.scalars(select(User).order_by(User.id)).all()
