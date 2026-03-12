from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from . import models, schemas
from .config import settings
from .security import decrypt_secret, encrypt_secret, get_password_hash


def get_admin_by_username(db: Session, username: str) -> models.Admin | None:
    return db.scalar(select(models.Admin).where(models.Admin.username == username))


def get_admin_by_id(db: Session, admin_id: int) -> models.Admin | None:
    return db.get(models.Admin, admin_id)


def create_admin(db: Session, username: str, password: str) -> models.Admin:
    admin = models.Admin(
        username=username.strip(),
        password_hash=get_password_hash(password),
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def update_admin_last_login(db: Session, admin: models.Admin) -> models.Admin:
    admin.last_login_at = datetime.now(timezone.utc)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def update_admin_password(db: Session, admin: models.Admin, password: str) -> models.Admin:
    admin.password_hash = get_password_hash(password)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def list_managed_apis(db: Session, is_active: bool | None = None, query: str | None = None) -> list[models.ManagedAPI]:
    stmt: Select[tuple[models.ManagedAPI]] = select(models.ManagedAPI).order_by(models.ManagedAPI.created_at.desc())
    if is_active is not None:
        stmt = stmt.where(models.ManagedAPI.is_active == is_active)
    if query:
        like_term = f"%{query.strip()}%"
        stmt = stmt.where(models.ManagedAPI.name.ilike(like_term))
    return list(db.scalars(stmt).all())


def get_managed_api(db: Session, api_id: int) -> models.ManagedAPI | None:
    return db.get(models.ManagedAPI, api_id)


def get_managed_api_by_name(db: Session, name: str) -> models.ManagedAPI | None:
    return db.scalar(select(models.ManagedAPI).where(models.ManagedAPI.name == name.strip()))


def create_managed_api(db: Session, payload: schemas.ManagedAPICreate) -> models.ManagedAPI:
    item = models.ManagedAPI(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_managed_api(db: Session, item: models.ManagedAPI, payload: schemas.ManagedAPIUpdate) -> models.ManagedAPI:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def delete_managed_api(db: Session, item: models.ManagedAPI) -> None:
    db.delete(item)
    db.commit()


def list_db_connections(
    db: Session,
    is_active: bool | None = None,
    query: str | None = None,
) -> list[models.DBConnection]:
    stmt: Select[tuple[models.DBConnection]] = select(models.DBConnection).order_by(models.DBConnection.created_at.desc())
    if is_active is not None:
        stmt = stmt.where(models.DBConnection.is_active == is_active)
    if query:
        like_term = f"%{query.strip()}%"
        stmt = stmt.where(models.DBConnection.name.ilike(like_term))
    return list(db.scalars(stmt).all())


def get_db_connection(db: Session, connection_id: int) -> models.DBConnection | None:
    return db.get(models.DBConnection, connection_id)


def get_db_connection_by_name(db: Session, name: str) -> models.DBConnection | None:
    return db.scalar(select(models.DBConnection).where(models.DBConnection.name == name.strip()))


def create_db_connection(db: Session, payload: schemas.DBConnectionCreate) -> models.DBConnection:
    values = payload.model_dump(exclude={"password"})
    values["password_encrypted"] = encrypt_secret(payload.password) if payload.password else None
    item = models.DBConnection(**values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_db_connection(
    db: Session,
    item: models.DBConnection,
    payload: schemas.DBConnectionUpdate,
) -> models.DBConnection:
    values = payload.model_dump(exclude_unset=True, exclude={"password"})
    for field, value in values.items():
        setattr(item, field, value)

    if "password" in payload.model_fields_set:
        item.password_encrypted = encrypt_secret(payload.password) if payload.password else None

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_db_connection_test_result(
    db: Session,
    item: models.DBConnection,
    success: bool,
    message: str,
) -> models.DBConnection:
    item.last_tested_at = datetime.now(timezone.utc)
    item.last_test_status = "success" if success else "failed"
    item.last_test_message = message
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def delete_db_connection(db: Session, item: models.DBConnection) -> None:
    db.delete(item)
    db.commit()


def serialize_db_connection(item: models.DBConnection) -> schemas.DBConnectionResponse:
    return schemas.DBConnectionResponse(
        id=item.id,
        name=item.name,
        db_type=item.db_type,
        host=item.host,
        port=item.port,
        db_name=item.db_name,
        username=item.username,
        description=item.description,
        is_active=item.is_active,
        has_password=bool(item.password_encrypted),
        password_masked="********" if item.password_encrypted else "",
        last_tested_at=item.last_tested_at,
        last_test_status=item.last_test_status,
        last_test_message=item.last_test_message,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def get_db_connection_secret(item: models.DBConnection) -> str | None:
    if not item.password_encrypted:
        return None
    return decrypt_secret(item.password_encrypted)


def create_activity_log(
    db: Session,
    *,
    log_type: schemas.LogType,
    message: str,
    is_success: bool,
    level: schemas.LogLevel = "info",
    status_code: int | None = None,
    detail: str | None = None,
    api_id: int | None = None,
    db_connection_id: int | None = None,
) -> models.ActivityLog:
    entry = models.ActivityLog(
        log_type=log_type,
        message=message,
        is_success=is_success,
        level=level,
        status_code=status_code,
        detail=detail,
        api_id=api_id,
        db_connection_id=db_connection_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def build_log_response(item: models.ActivityLog) -> schemas.ActivityLogResponse:
    return schemas.ActivityLogResponse(
        id=item.id,
        log_type=item.log_type,
        api_id=item.api_id,
        api_name=item.api.name if item.api else None,
        db_connection_id=item.db_connection_id,
        db_connection_name=item.db_connection.name if item.db_connection else None,
        level=item.level,
        status_code=item.status_code,
        is_success=item.is_success,
        message=item.message,
        detail=item.detail,
        created_at=item.created_at,
    )


def list_activity_logs(
    db: Session,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    api_id: int | None = None,
    api_name: str | None = None,
    status_code: int | None = None,
    is_success: bool | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> tuple[list[models.ActivityLog], int]:
    actual_page_size = page_size or settings.log_page_size_default

    stmt = (
        select(models.ActivityLog)
        .options(joinedload(models.ActivityLog.api), joinedload(models.ActivityLog.db_connection))
        .order_by(models.ActivityLog.created_at.desc())
    )
    count_stmt = select(func.count(models.ActivityLog.id))

    filters = []
    if date_from is not None:
        filters.append(models.ActivityLog.created_at >= date_from)
    if date_to is not None:
        filters.append(models.ActivityLog.created_at <= date_to)
    if api_id is not None:
        filters.append(models.ActivityLog.api_id == api_id)
    if api_name:
        stmt = stmt.join(models.ManagedAPI, models.ActivityLog.api_id == models.ManagedAPI.id)
        count_stmt = count_stmt.join(models.ManagedAPI, models.ActivityLog.api_id == models.ManagedAPI.id)
        filters.append(models.ManagedAPI.name.ilike(f"%{api_name.strip()}%"))
    if status_code is not None:
        filters.append(models.ActivityLog.status_code == status_code)
    if is_success is not None:
        filters.append(models.ActivityLog.is_success == is_success)

    for predicate in filters:
        stmt = stmt.where(predicate)
        count_stmt = count_stmt.where(predicate)

    stmt = stmt.offset((page - 1) * actual_page_size).limit(actual_page_size)
    items = list(db.scalars(stmt).all())
    total = db.scalar(count_stmt) or 0
    return items, total


def get_dashboard_summary(db: Session) -> schemas.DashboardSummaryResponse:
    since = datetime.now(timezone.utc) - timedelta(days=settings.dashboard_window_days)

    success_count = db.scalar(
        select(func.count(models.ActivityLog.id)).where(
            models.ActivityLog.created_at >= since,
            models.ActivityLog.is_success.is_(True),
            models.ActivityLog.log_type == "api",
        )
    ) or 0

    failure_count = db.scalar(
        select(func.count(models.ActivityLog.id)).where(
            models.ActivityLog.created_at >= since,
            models.ActivityLog.is_success.is_(False),
            models.ActivityLog.log_type == "api",
        )
    ) or 0

    api_count = db.scalar(select(func.count(models.ManagedAPI.id))) or 0
    db_connection_count = db.scalar(select(func.count(models.DBConnection.id))) or 0

    recent_errors = list(
        db.scalars(
            select(models.ActivityLog)
            .options(joinedload(models.ActivityLog.api), joinedload(models.ActivityLog.db_connection))
            .where(models.ActivityLog.is_success.is_(False))
            .order_by(models.ActivityLog.created_at.desc())
            .limit(5)
        ).all()
    )

    return schemas.DashboardSummaryResponse(
        recent_success_count=success_count,
        recent_failure_count=failure_count,
        api_count=api_count,
        db_connection_count=db_connection_count,
        recent_error_logs=[build_log_response(item) for item in recent_errors],
    )
