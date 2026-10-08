"""Create the bootstrap ADMIN account from FIRST_ADMIN_EMAIL / FIRST_ADMIN_PASSWORD."""

import logging

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.database import SessionLocal
from app.models.enums import UserRole
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


def ensure_admin() -> None:
    settings = get_settings()
    if not settings.FIRST_ADMIN_EMAIL or not settings.FIRST_ADMIN_PASSWORD:
        logger.warning("FIRST_ADMIN_EMAIL / FIRST_ADMIN_PASSWORD not set - skipping admin bootstrap")
        return
    with SessionLocal() as db:
        created = AuthService(db).ensure_user(
            settings.FIRST_ADMIN_EMAIL, settings.FIRST_ADMIN_PASSWORD, settings.FIRST_ADMIN_NAME, UserRole.ADMIN
        )
    logger.info("Admin account %s %s", settings.FIRST_ADMIN_EMAIL, "created" if created else "already exists")


if __name__ == "__main__":
    configure_logging()
    ensure_admin()
