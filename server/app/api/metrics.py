from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.health import MetricSnapshot, classify_client_health
from app.core.websocket import manager
from app.models.client import ClientRecord
from app.models.event import EventRecord
from app.models.metric import ClientMetricIn, ClientMetricRecord

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.post("/")
async def create_metric(
    payload: ClientMetricIn,
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    client = await session.get(ClientRecord, payload.client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client must be registered before uploading metrics")

    metric = ClientMetricRecord(
        client_id=payload.client_id,
        ts=payload.timestamp,
        latency_ms=payload.latency_ms,
        jitter_ms=payload.jitter_ms,
        packet_loss_percent=payload.packet_loss_percent,
        tx_mbps=payload.tx_mbps,
        rx_mbps=payload.rx_mbps,
        server_reachable=payload.server_reachable,
        game_server_latency_ms=payload.game_server_latency_ms,
        game_server_packet_loss_percent=payload.game_server_packet_loss_percent,
    )
    session.add(metric)

    previous_status = client.last_status
    current_status = classify_client_health(
        MetricSnapshot(
            latency_ms=payload.latency_ms,
            jitter_ms=payload.jitter_ms,
            packet_loss_percent=payload.packet_loss_percent,
        )
    )
    client.last_seen = datetime.now(timezone.utc)
    client.last_status = current_status
    client.last_metrics_payload = payload.model_dump(mode="json")
    if payload.local_ip is not None:
        client.local_ip = payload.local_ip
    if payload.interface_name is not None:
        client.interface_name = payload.interface_name

    if current_status != previous_status:
        session.add(
            EventRecord(
                severity="warning" if current_status in {"yellow", "red"} else "info",
                client_id=payload.client_id,
                event_type="health_changed",
                message=f"{client.hostname} health changed from {previous_status} to {current_status}.",
                data={"from": previous_status, "to": current_status},
            )
        )

    await session.commit()
    await manager.broadcast_json(
        {
            "type": "client_metrics",
            "client_id": str(payload.client_id),
            "metrics": {
                "latency_ms": payload.latency_ms,
                "jitter_ms": payload.jitter_ms,
                "packet_loss_percent": payload.packet_loss_percent,
                "tx_mbps": payload.tx_mbps,
                "rx_mbps": payload.rx_mbps,
                "health": current_status,
                "timestamp": payload.timestamp.isoformat(),
            },
        }
    )
    return {"ok": True}
