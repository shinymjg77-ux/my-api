from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db
from ..deps import CurrentAdmin
from ..services import db_test_service, log_service


router = APIRouter(prefix="/db-connections", tags=["db-connections"])


@router.get("", response_model=list[schemas.DBConnectionResponse])
def list_connections(
    _: CurrentAdmin,
    db: Session = Depends(get_db),
    is_active: bool | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=100),
) -> list[schemas.DBConnectionResponse]:
    items = crud.list_db_connections(db, is_active=is_active, query=q)
    return [crud.serialize_db_connection(item) for item in items]


@router.post("", response_model=schemas.DBConnectionResponse, status_code=status.HTTP_201_CREATED)
def create_connection(
    payload: schemas.DBConnectionCreate,
    _: CurrentAdmin,
    db: Session = Depends(get_db),
) -> schemas.DBConnectionResponse:
    if crud.get_db_connection_by_name(db, payload.name):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connection name already exists")
    item = crud.create_db_connection(db, payload)
    return crud.serialize_db_connection(item)


@router.get("/{connection_id}", response_model=schemas.DBConnectionResponse)
def get_connection(
    connection_id: int,
    _: CurrentAdmin,
    db: Session = Depends(get_db),
) -> schemas.DBConnectionResponse:
    item = crud.get_db_connection(db, connection_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    return crud.serialize_db_connection(item)


@router.put("/{connection_id}", response_model=schemas.DBConnectionResponse)
def update_connection(
    connection_id: int,
    payload: schemas.DBConnectionUpdate,
    _: CurrentAdmin,
    db: Session = Depends(get_db),
) -> schemas.DBConnectionResponse:
    item = crud.get_db_connection(db, connection_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    if payload.name and payload.name != item.name:
        existing = crud.get_db_connection_by_name(db, payload.name)
        if existing and existing.id != connection_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connection name already exists")

    item = crud.update_db_connection(db, item, payload)
    return crud.serialize_db_connection(item)


@router.delete("/{connection_id}", response_model=schemas.MessageResponse)
def delete_connection(
    connection_id: int,
    _: CurrentAdmin,
    db: Session = Depends(get_db),
) -> schemas.MessageResponse:
    item = crud.get_db_connection(db, connection_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    crud.delete_db_connection(db, item)
    return schemas.MessageResponse(message="Connection deleted")


@router.post("/test", response_model=schemas.DBConnectionTestResponse)
def test_connection_payload(
    payload: schemas.DBConnectionTestRequest,
    _: CurrentAdmin,
    db: Session = Depends(get_db),
) -> schemas.DBConnectionTestResponse:
    success, message, latency_ms = db_test_service.test_database_connection(payload)
    log_service.log_db_test_result(
        db,
        db_connection_id=None,
        success=success,
        message="Ad-hoc DB connection test succeeded" if success else "Ad-hoc DB connection test failed",
        detail=message,
    )
    return schemas.DBConnectionTestResponse(success=success, message=message, latency_ms=latency_ms)


@router.post("/{connection_id}/test", response_model=schemas.DBConnectionTestResponse)
def test_saved_connection(
    connection_id: int,
    _: CurrentAdmin,
    db: Session = Depends(get_db),
) -> schemas.DBConnectionTestResponse:
    item = crud.get_db_connection(db, connection_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    payload = schemas.DBConnectionTestRequest(
        db_type=item.db_type,
        host=item.host,
        port=item.port,
        db_name=item.db_name,
        username=item.username,
        password=crud.get_db_connection_secret(item),
    )
    success, message, latency_ms = db_test_service.test_database_connection(payload)
    crud.update_db_connection_test_result(db, item, success=success, message=message)
    log_service.log_db_test_result(
        db,
        db_connection_id=item.id,
        success=success,
        message=f"Saved DB connection test {'succeeded' if success else 'failed'}: {item.name}",
        detail=message,
    )
    return schemas.DBConnectionTestResponse(success=success, message=message, latency_ms=latency_ms)
