from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    status: str
    service: str
    version: str


class DependencyStatus(BaseModel):
    mysql: str
    redis: str
    elasticsearch: str


class ReadyResponse(BaseModel):
    status: str
    dependencies: DependencyStatus


@router.get("/live", response_model=LiveResponse)
def live() -> LiveResponse:
    settings = get_settings()
    return LiveResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )


@router.get("/ready", response_model=ReadyResponse)
def ready() -> ReadyResponse:
    return ReadyResponse(
        status="degraded",
        dependencies=DependencyStatus(
            mysql="not_checked",
            redis="not_checked",
            elasticsearch="not_checked",
        ),
    )

