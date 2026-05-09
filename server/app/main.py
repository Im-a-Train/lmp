from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, select
from starlette.websockets import WebSocketDisconnect

from app.api.clients import router as clients_router
from app.api.config import router as config_router
from app.api.dashboard import router as dashboard_router
from app.api.downloads import router as downloads_router
from app.api.events import router as events_router
from app.api.metrics import process_metric, router as metrics_router
from app.core.config import Settings, settings
from app.core.database import database
from app.core.mdns import start_mdns, stop_mdns
from app.core.udp_echo import start_udp_echo_server
from app.core.websocket import manager
from app.models.client import ClientRecord
from app.models.event import EventRecord
from app.models.metric import ClientMetricIn, ClientMetricRecord


async def offline_monitor(stop_event: asyncio.Event, app_settings: Settings) -> None:
    while not stop_event.is_set():
        async for session in database.session():
            cutoff = datetime.now(timezone.utc) - timedelta(
                seconds=app_settings.client_offline_after_seconds
            )
            clients = list(
                (
                    await session.scalars(
                        select(ClientRecord).where(
                            ClientRecord.last_seen < cutoff,
                            ClientRecord.last_status != "offline",
                        )
                    )
                ).all()
            )
            for client in clients:
                client.last_status = "offline"
                session.add(
                    EventRecord(
                        severity="warning",
                        client_id=client.client_id,
                        event_type="client_offline",
                        message=f"{client.hostname} has gone offline.",
                        data={"last_seen": client.last_seen.isoformat()},
                    )
                )
            if clients:
                await session.commit()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=2)
        except TimeoutError:
            continue


async def retention_cleanup(stop_event: asyncio.Event, app_settings: Settings) -> None:
    while not stop_event.is_set():
        async for session in database.session():
            metrics_cutoff = datetime.now(timezone.utc) - timedelta(days=app_settings.retention_days)
            events_cutoff = datetime.now(timezone.utc) - timedelta(days=app_settings.event_retention_days)
            await session.execute(delete(ClientMetricRecord).where(ClientMetricRecord.ts < metrics_cutoff))
            await session.execute(delete(EventRecord).where(EventRecord.ts < events_cutoff))
            await session.commit()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3600)
        except TimeoutError:
            continue


def _public_port(base_url: str) -> int:
    try:
        return int(base_url.rstrip("/").rsplit(":", 1)[-1])
    except (ValueError, IndexError):
        return 8080


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_settings: Settings = app.state.settings
    database.configure(app_settings.database_url)
    await database.init_models()

    stop_event = asyncio.Event()
    udp_transport = await start_udp_echo_server(app_settings.udp_echo_host, app_settings.udp_echo_port)
    offline_task = asyncio.create_task(offline_monitor(stop_event, app_settings))
    cleanup_task = asyncio.create_task(retention_cleanup(stop_event, app_settings))
    app.state.stop_event = stop_event
    app.state.udp_transport = udp_transport
    app.state.background_tasks = [offline_task, cleanup_task]

    mdns_zc, mdns_info = await start_mdns(
        app_settings.app_name,
        _public_port(app_settings.public_base_url),
    )

    try:
        yield
    finally:
        stop_event.set()
        udp_transport.close()
        for task in app.state.background_tasks:
            task.cancel()
        await asyncio.gather(*app.state.background_tasks, return_exceptions=True)
        await stop_mdns(mdns_zc, mdns_info)
        await database.dispose()


def create_app(app_settings: Settings = settings) -> FastAPI:
    app = FastAPI(title="LAN Pulse API", version="0.1.0", lifespan=lifespan)
    app.state.settings = app_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[app_settings.public_base_url, "http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(config_router)
    app.include_router(clients_router)
    app.include_router(metrics_router)
    app.include_router(events_router)
    app.include_router(downloads_router)
    app.include_router(dashboard_router)

    @app.websocket("/ws/dashboard")
    async def dashboard_websocket(websocket: WebSocket) -> None:
        await manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    @app.websocket("/ws/client")
    async def client_websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    payload = ClientMetricIn.model_validate_json(data)
                except Exception:
                    continue
                try:
                    async for session in database.session():
                        await process_metric(payload, session)
                except ValueError:
                    pass
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    web_dist = app_settings.web_dist_dir
    assets_dir = web_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    async def root():
        index_file = web_dist / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse({"status": "ready", "message": "Web UI build not found."})

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        candidate = web_dist / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        index_file = web_dist / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse({"status": "ready", "path": full_path})

    return app


app = create_app()
