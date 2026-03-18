import hmac
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from . import crud
from .config import settings
from .database import get_db
from .models import Admin
from .security import safe_decode_token


DBSession = Annotated[Session, Depends(get_db)]


def get_current_admin(
    db: DBSession,
    session_token: Annotated[str | None, Cookie(alias=settings.admin_cookie_name)] = None,
) -> Admin:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    payload = safe_decode_token(session_token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    admin = crud.get_admin_by_username(db, payload["sub"])
    if not admin or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive admin")

    return admin


CurrentAdmin = Annotated[Admin, Depends(get_current_admin)]


def require_job_secret(job_secret: Annotated[str | None, Header(alias="X-Job-Secret")] = None) -> str:
    if not job_secret or not hmac.compare_digest(job_secret, settings.job_shared_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid job secret")
    return job_secret
