from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import create_app


@pytest.fixture()
def app_settings(tmp_path: Path):
    settings.database_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    settings.udp_echo_port = 0
    settings.downloads_dir = tmp_path / "downloads"
    settings.downloads_dir.mkdir()
    settings.web_dist_dir = tmp_path / "web-dist"
    settings.web_dist_dir.mkdir()
    return settings


@pytest.fixture()
async def client(app_settings):
    app = create_app(app_settings)
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as test_client:
            yield test_client


@pytest.mark.asyncio
async def test_register_metric_and_dashboard_flow(client: AsyncClient):
    client_id = str(uuid4())
    register_response = await client.post(
        "/api/clients/register",
        json={
            "client_id": client_id,
            "hostname": "PC-12",
            "username": "melvin",
            "os": "Windows 11",
            "client_version": "0.1.0",
            "local_ip": "192.168.1.42",
            "interface_name": "Ethernet",
        },
    )
    assert register_response.status_code == 200
    assert register_response.json()["accepted"] is True

    metric_response = await client.post(
        "/api/metrics/",
        json={
            "client_id": client_id,
            "timestamp": "2026-05-09T20:15:00Z",
            "latency_ms": 12.5,
            "jitter_ms": 1.4,
            "packet_loss_percent": 0.0,
            "tx_mbps": 8.3,
            "rx_mbps": 21.7,
            "server_reachable": True,
            "game_server_latency_ms": None,
            "game_server_packet_loss_percent": None,
            "local_ip": "192.168.1.42",
            "interface_name": "Ethernet",
        },
    )
    assert metric_response.status_code == 200
    assert metric_response.json() == {"ok": True}

    clients_response = await client.get("/api/clients/")
    assert clients_response.status_code == 200
    clients = clients_response.json()
    assert len(clients) == 1
    assert clients[0]["hostname"] == "PC-12"
    assert clients[0]["health"] == "yellow"

    detail_response = await client.get(f"/api/clients/{client_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["client"]["hostname"] == "PC-12"
    assert len(detail["metrics"]) == 1
    assert detail["last_metrics_payload"]["rx_mbps"] == 21.7

    dashboard_response = await client.get("/api/dashboard/")
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert dashboard["summary"]["online_clients"] == 1
    assert dashboard["summary"]["global_health"] == "yellow"


@pytest.mark.asyncio
async def test_download_endpoint_returns_404_when_artifact_missing(client: AsyncClient):
    response = await client.get("/downloads/client/latest")
    assert response.status_code == 404
