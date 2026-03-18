import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db


DBSession = Annotated[Session, Depends(get_db)]


def require_job_secret(job_secret: Annotated[str | None, Header(alias="X-Job-Secret")] = None) -> str:
    if not job_secret or not hmac.compare_digest(job_secret, settings.job_shared_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid job secret")
    return job_secret
