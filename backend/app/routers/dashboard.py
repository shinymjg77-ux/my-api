from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db
from ..deps import CurrentAdmin


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=schemas.DashboardSummaryResponse)
def dashboard_summary(
    _: CurrentAdmin,
    db: Session = Depends(get_db),
) -> schemas.DashboardSummaryResponse:
    return crud.get_dashboard_summary(db)
