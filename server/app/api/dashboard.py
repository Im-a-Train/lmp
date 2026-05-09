from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.clients import is_online, latest_metric_map
from app.core.database import get_session
from app.core.health import classify_global_health
from app.models.client import ClientRecord, ClientSummary
from app.models.event import EventRecord, EventView
from app.models.metric import DashboardSummary

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/")
async def get_dashboard(session: AsyncSession = Depends(get_session)) -> dict:
    clients = list((await session.scalars(select(ClientRecord).order_by(ClientRecord.hostname.asc()))).all())
    metrics = await latest_metric_map(session, [client.client_id for client in clients])

    online_clients: list[ClientSummary] = []
    offline_count = 0
    for client in clients:
        latest_metric = metrics.get(client.client_id)
        online = is_online(client.last_seen)
        if online:
            online_clients.append(
                ClientSummary(
                    client_id=client.client_id,
                    hostname=client.hostname,
                    username=client.username,
                    local_ip=client.local_ip,
                    health=client.last_status,
                    latency_ms=latest_metric.latency_ms if latest_metric else None,
                    jitter_ms=latest_metric.jitter_ms if latest_metric else None,
                    packet_loss_percent=latest_metric.packet_loss_percent if latest_metric else None,
                    tx_mbps=latest_metric.tx_mbps if latest_metric else None,
                    rx_mbps=latest_metric.rx_mbps if latest_metric else None,
                )
            )
        else:
            offline_count += 1

    total = len(clients)
    offline_ratio = (offline_count / total) if total else 0.0
    summary = DashboardSummary(
        online_clients=len(online_clients),
        offline_clients=offline_count,
        global_health=classify_global_health([client.health for client in online_clients], offline_ratio),
        worst_latency_clients=[
            client.model_dump(mode="json")
            for client in sorted(
                [item for item in online_clients if item.latency_ms is not None],
                key=lambda item: item.latency_ms or 0,
                reverse=True,
            )[:5]
        ],
        packet_loss_alerts=[
            client.model_dump(mode="json")
            for client in online_clients
            if (client.packet_loss_percent or 0) > 0
        ][:5],
        jitter_alerts=[
            client.model_dump(mode="json")
            for client in sorted(
                [item for item in online_clients if item.jitter_ms is not None and item.jitter_ms > 2],
                key=lambda item: item.jitter_ms or 0,
                reverse=True,
            )[:5]
        ],
        top_bandwidth_users=[
            client.model_dump(mode="json")
            for client in sorted(
                online_clients,
                key=lambda item: (item.tx_mbps or 0) + (item.rx_mbps or 0),
                reverse=True,
            )[:5]
        ],
    )

    recent_events = list(
        (
            await session.scalars(
                select(EventRecord).order_by(EventRecord.ts.desc()).limit(10)
            )
        ).all()
    )
    return {
        "summary": summary.model_dump(mode="json"),
        "recent_events": [
            EventView(
                id=event.id,
                ts=event.ts,
                severity=event.severity,
                client_id=event.client_id,
                event_type=event.event_type,
                message=event.message,
                data=event.data,
            ).model_dump(mode="json")
            for event in recent_events
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_start": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
    }
