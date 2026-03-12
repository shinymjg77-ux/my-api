from sqlalchemy import select
from sqlalchemy.orm import Session

from . import crud, models
from .config import settings


def bootstrap_admin(db: Session) -> None:
    existing_admin = db.scalar(select(models.Admin.id).limit(1))
    if existing_admin:
        return

    if not settings.bootstrap_admin_username or not settings.bootstrap_admin_password:
        raise RuntimeError(
            "No admin account exists. Set BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD in .env."
        )

    crud.create_admin(
        db,
        username=settings.bootstrap_admin_username,
        password=settings.bootstrap_admin_password,
    )
