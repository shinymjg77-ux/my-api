from sqlalchemy.orm import Session

from .. import crud


def log_auth_success(db: Session, username: str) -> None:
    crud.create_activity_log(
        db,
        log_type="auth",
        message=f"Admin login succeeded: {username}",
        is_success=True,
        level="info",
        status_code=200,
    )


def log_auth_failure(db: Session, username: str) -> None:
    crud.create_activity_log(
        db,
        log_type="auth",
        message=f"Admin login failed: {username}",
        is_success=False,
        level="warning",
        status_code=401,
    )


def log_password_change(db: Session, username: str, *, success: bool, detail: str | None = None) -> None:
    crud.create_activity_log(
        db,
        log_type="auth",
        message=f"Admin password change {'succeeded' if success else 'failed'}: {username}",
        is_success=success,
        level="info" if success else "warning",
        status_code=200 if success else 400,
        detail=detail,
    )


def log_db_test_result(
    db: Session,
    *,
    db_connection_id: int | None,
    success: bool,
    message: str,
    detail: str | None = None,
) -> None:
    crud.create_activity_log(
        db,
        log_type="db",
        message=message,
        is_success=success,
        level="info" if success else "error",
        status_code=200 if success else 500,
        detail=detail,
        db_connection_id=db_connection_id,
    )


def log_system_error(db: Session, message: str, detail: str | None = None) -> None:
    crud.create_activity_log(
        db,
        log_type="system",
        message=message,
        is_success=False,
        level="error",
        status_code=500,
        detail=detail,
    )
