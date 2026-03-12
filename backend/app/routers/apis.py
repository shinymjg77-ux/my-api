from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..database import get_db
from ..deps import CurrentAdmin


router = APIRouter(prefix="/apis", tags=["apis"])


@router.get("", response_model=list[schemas.ManagedAPIResponse])
def list_apis(
    _: CurrentAdmin,
    db: Session = Depends(get_db),
    is_active: bool | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=100),
) -> list[schemas.ManagedAPIResponse]:
    items = crud.list_managed_apis(db, is_active=is_active, query=q)
    return [schemas.ManagedAPIResponse.model_validate(item) for item in items]


@router.post("", response_model=schemas.ManagedAPIResponse, status_code=status.HTTP_201_CREATED)
def create_api(
    payload: schemas.ManagedAPICreate,
    _: CurrentAdmin,
    db: Session = Depends(get_db),
) -> schemas.ManagedAPIResponse:
    if crud.get_managed_api_by_name(db, payload.name):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="API name already exists")
    item = crud.create_managed_api(db, payload)
    return schemas.ManagedAPIResponse.model_validate(item)


@router.get("/{api_id}", response_model=schemas.ManagedAPIResponse)
def get_api(
    api_id: int,
    _: CurrentAdmin,
    db: Session = Depends(get_db),
) -> schemas.ManagedAPIResponse:
    item = crud.get_managed_api(db, api_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API not found")
    return schemas.ManagedAPIResponse.model_validate(item)


@router.put("/{api_id}", response_model=schemas.ManagedAPIResponse)
def update_api(
    api_id: int,
    payload: schemas.ManagedAPIUpdate,
    _: CurrentAdmin,
    db: Session = Depends(get_db),
) -> schemas.ManagedAPIResponse:
    item = crud.get_managed_api(db, api_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API not found")

    if payload.name and payload.name != item.name:
        existing = crud.get_managed_api_by_name(db, payload.name)
        if existing and existing.id != api_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="API name already exists")

    item = crud.update_managed_api(db, item, payload)
    return schemas.ManagedAPIResponse.model_validate(item)


@router.delete("/{api_id}", response_model=schemas.MessageResponse)
def delete_api(
    api_id: int,
    _: CurrentAdmin,
    db: Session = Depends(get_db),
) -> schemas.MessageResponse:
    item = crud.get_managed_api(db, api_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API not found")
    crud.delete_managed_api(db, item)
    return schemas.MessageResponse(message="API deleted")
