from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from .. import crud, schemas
from ..config import settings
from ..database import get_db
from ..deps import CurrentAdmin
from ..security import create_access_token, verify_password
from ..services import log_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.AdminResponse)
def login(
    payload: schemas.AdminLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> schemas.AdminResponse:
    admin = crud.get_admin_by_username(db, payload.username.strip())
    if not admin or not verify_password(payload.password, admin.password_hash):
        log_service.log_auth_failure(db, payload.username.strip())
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    if not admin.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin is inactive")

    token = create_access_token(admin.username)
    response.set_cookie(
        key=settings.admin_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )

    admin = crud.update_admin_last_login(db, admin)
    log_service.log_auth_success(db, admin.username)
    return schemas.AdminResponse.model_validate(admin)


@router.post("/logout", response_model=schemas.MessageResponse)
def logout(response: Response) -> schemas.MessageResponse:
    response.delete_cookie(
        key=settings.admin_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    return schemas.MessageResponse(message="Logged out")


@router.get("/me", response_model=schemas.AdminResponse)
def me(current_admin: CurrentAdmin) -> schemas.AdminResponse:
    return schemas.AdminResponse.model_validate(current_admin)


@router.post("/change-password", response_model=schemas.MessageResponse)
def change_password(
    payload: schemas.AdminPasswordChangeRequest,
    current_admin: CurrentAdmin,
    db: Session = Depends(get_db),
) -> schemas.MessageResponse:
    if not verify_password(payload.current_password, current_admin.password_hash):
        log_service.log_password_change(
            db,
            current_admin.username,
            success=False,
            detail="Current password did not match",
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password confirmation does not match")

    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be different")

    crud.update_admin_password(db, current_admin, payload.new_password)
    log_service.log_password_change(db, current_admin.username, success=True)
    return schemas.MessageResponse(message="Password updated")
