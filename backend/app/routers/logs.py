from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..config import settings
from ..database import get_db
from ..deps import CurrentAdmin


router = APIRouter(prefix="/logs", tags=["logs"])


def _to_start_of_day(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return normalized.replace(hour=0, minute=0, second=0, microsecond=0)


def _to_end_of_day(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return normalized.replace(hour=23, minute=59, second=59, microsecond=999999)


@router.get("", response_model=schemas.ActivityLogListResponse)
def list_logs(
    _: CurrentAdmin,
    db: Session = Depends(get_db),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    api_id: int | None = Query(default=None),
    api_name: str | None = Query(default=None, min_length=1, max_length=100),
    status_code: int | None = Query(default=None),
    is_success: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=settings.log_page_size_default, ge=1, le=settings.log_page_size_max),
) -> schemas.ActivityLogListResponse:
    items, total = crud.list_activity_logs(
        db,
        date_from=_to_start_of_day(date_from),
        date_to=_to_end_of_day(date_to),
        api_id=api_id,
        api_name=api_name,
        status_code=status_code,
        is_success=is_success,
        page=page,
        page_size=page_size,
    )
    return schemas.ActivityLogListResponse(
        items=[crud.build_log_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
