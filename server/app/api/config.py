from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
async def get_config() -> dict[str, str | int]:
    return {
        "server_name": settings.app_name,
        "metrics_interval_seconds": settings.metrics_interval_seconds,
        "udp_echo_port": settings.udp_echo_port,
        "client_min_version": settings.client_min_version,
    }


@router.get("/ping")
async def ping() -> dict[str, str]:
    return {"status": "ok"}
