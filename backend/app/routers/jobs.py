from fastapi import APIRouter, Depends

from ..deps import DBSession, require_job_secret
from ..schemas import OpsCheckResponse
from ..services.ops_check_service import run_ops_check


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/ops-check", response_model=OpsCheckResponse)
def ops_check(
    db: DBSession,
    _: str = Depends(require_job_secret),
) -> OpsCheckResponse:
    return run_ops_check(db)
