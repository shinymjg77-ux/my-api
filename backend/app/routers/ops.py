from fastapi import APIRouter, Depends

from ..deps import require_ops_command_secret
from ..schemas import OpsCommandRequest, OpsCommandResponse
from ..services.ops_command_service import execute_ops_command


router = APIRouter(prefix="/ops", tags=["ops"])


@router.post("/command", response_model=OpsCommandResponse)
def ops_command(
    payload: OpsCommandRequest,
    _: str = Depends(require_ops_command_secret),
) -> OpsCommandResponse:
    return execute_ops_command(payload)
