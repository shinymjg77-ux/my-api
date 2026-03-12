from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db
from ..deps import CurrentAdmin
from ..services.ops_dashboard_service import get_ops_dashboard_overview, get_runtime_logs


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=schemas.DashboardSummaryResponse)
def dashboard_summary(
    _: CurrentAdmin,
    db: Session = Depends(get_db),
) -> schemas.DashboardSummaryResponse:
    return crud.get_dashboard_summary(db)


@router.get("/overview", response_model=schemas.OpsDashboardResponse)
def dashboard_overview(_: CurrentAdmin) -> schemas.OpsDashboardResponse:
    return get_ops_dashboard_overview()


@router.get("/runtime-logs", response_model=schemas.RuntimeLogsResponse)
def dashboard_runtime_logs(_: CurrentAdmin) -> schemas.RuntimeLogsResponse:
    return get_runtime_logs()
