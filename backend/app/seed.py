from sqlalchemy import select
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .config import settings


def bootstrap_admin(db: Session) -> None:
    existing_admin = db.scalar(select(models.Admin.id).limit(1))
    if existing_admin:
        return

    if not settings.bootstrap_admin_username or not settings.bootstrap_admin_password:
        raise RuntimeError(
            "No admin account exists. Set BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD in .env."
        )

    crud.create_admin(
        db,
        username=settings.bootstrap_admin_username,
        password=settings.bootstrap_admin_password,
    )


def _build_managed_api_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def get_default_managed_apis() -> list[schemas.ManagedAPICreate]:
    admin_base = settings.managed_api_admin_base_url
    market_base = settings.managed_api_market_base_url

    return [
        schemas.ManagedAPICreate(
            name="Admin Health",
            group_path="platform/admin",
            url=_build_managed_api_url(admin_base, "/healthz"),
            method="GET",
            description="관리자 백엔드 헬스체크",
            is_active=True,
        ),
        schemas.ManagedAPICreate(
            name="Dashboard Summary",
            group_path="platform/admin/dashboard",
            url=_build_managed_api_url(admin_base, f"{settings.api_prefix}/dashboard/summary"),
            method="GET",
            description="관리자 대시보드 요약 정보",
            is_active=True,
        ),
        schemas.ManagedAPICreate(
            name="Runtime Overview",
            group_path="platform/admin/dashboard",
            url=_build_managed_api_url(admin_base, f"{settings.api_prefix}/dashboard/overview"),
            method="GET",
            description="운영 상태 개요",
            is_active=True,
        ),
        schemas.ManagedAPICreate(
            name="Ops Check Job",
            group_path="platform/admin/jobs",
            url=_build_managed_api_url(admin_base, f"{settings.api_prefix}/jobs/ops-check"),
            method="GET",
            description="운영 이상 징후 체크 잡",
            is_active=True,
        ),
        schemas.ManagedAPICreate(
            name="Market API Health",
            group_path="market/health",
            url=_build_managed_api_url(market_base, "/healthz"),
            method="GET",
            description="시장 신호 서비스 헬스체크",
            is_active=True,
        ),
        schemas.ManagedAPICreate(
            name="Morning Briefing",
            group_path="market/briefings",
            url=_build_managed_api_url(market_base, f"{settings.api_prefix}/briefings/morning"),
            method="GET",
            description="미국 증시 마감 브리핑 데이터",
            is_active=True,
        ),
        schemas.ManagedAPICreate(
            name="QLD RSI Check",
            group_path="market/signals",
            url=_build_managed_api_url(market_base, f"{settings.api_prefix}/jobs/rsi-check"),
            method="POST",
            description="QLD RSI 상태 전이 체크 실행",
            is_active=True,
        ),
        schemas.ManagedAPICreate(
            name="Market Current Status",
            group_path="market/status",
            url=_build_managed_api_url(market_base, f"{settings.api_prefix}/status/current"),
            method="GET",
            description="현재 QLD RSI 상태 조회",
            is_active=True,
        ),
        schemas.ManagedAPICreate(
            name="Market Status History",
            group_path="market/status",
            url=_build_managed_api_url(market_base, f"{settings.api_prefix}/status/history"),
            method="GET",
            description="QLD RSI 상태 이력 조회",
            is_active=True,
        ),
    ]


def bootstrap_managed_apis(db: Session) -> None:
    defaults = get_default_managed_apis()
    existing_names = {
        name
        for (name,) in db.execute(
            select(models.ManagedAPI.name).where(
                models.ManagedAPI.name.in_([item.name for item in defaults])
            )
        ).all()
    }

    created = False
    for payload in defaults:
        if payload.name in existing_names:
            continue
        db.add(models.ManagedAPI(**payload.model_dump()))
        created = True

    if created:
        db.commit()
