from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings

router = APIRouter(prefix="/downloads", tags=["downloads"])


@router.get("/client/latest")
async def download_latest() -> FileResponse:
    artifact = settings.downloads_dir / "client-latest.exe"
    if not artifact.exists():
        raise HTTPException(status_code=404, detail="No client installer is available yet.")
    return FileResponse(
        artifact,
        media_type="application/vnd.microsoft.portable-executable",
        filename="client-latest.exe",
    )
