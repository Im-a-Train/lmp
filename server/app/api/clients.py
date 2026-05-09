from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.models.client import (
    ClientListItem,
    ClientMetadata,
    ClientRecord,
    ClientRegistrationRequest,
    ClientRegistrationResponse,
)
from app.models.event import EventRecord, EventView
from app.models.metric import ClientMetricPoint, ClientMetricRecord

router = APIRouter(prefix="/api/clients", tags=["clients"])


def is_online(last_seen: datetime) -> bool:
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - last_seen <= timedelta(
        seconds=settings.client_offline_after_seconds
    )


async def latest_metric_map(
    session: AsyncSession,
    client_ids: list[UUID],
) -> dict[UUID, ClientMetricRecord]:
    metrics_by_client: dict[UUID, ClientMetricRecord] = {}
    for client_id in client_ids:
        metric = await session.scalar(
            select(ClientMetricRecord)
            .where(ClientMetricRecord.client_id == client_id)
            .order_by(ClientMetricRecord.ts.desc())
            .limit(1)
        )
        if metric is not None:
            metrics_by_client[client_id] = metric
    return metrics_by_client


@router.post("/register", response_model=ClientRegistrationResponse)
async def register_client(
    payload: ClientRegistrationRequest,
    session: AsyncSession = Depends(get_session),
) -> ClientRegistrationResponse:
    client = await session.get(ClientRecord, payload.client_id)
    now = datetime.now(timezone.utc)
    if client is None:
        client = ClientRecord(
            client_id=payload.client_id,
            hostname=payload.hostname,
            username=payload.username,
            os=payload.os,
            client_version=payload.client_version,
            local_ip=payload.local_ip,
            interface_name=payload.interface_name,
            first_seen=now,
            last_seen=now,
            last_status="unknown",
        )
        session.add(client)
        session.add(
            EventRecord(
                severity="info",
                client_id=payload.client_id,
                event_type="client_registered",
                message=f"{payload.hostname} registered with the monitoring server.",
                data=payload.model_dump(mode="json"),
            )
        )
    else:
        client.hostname = payload.hostname
        client.username = payload.username
        client.os = payload.os
        client.client_version = payload.client_version
        client.local_ip = payload.local_ip
        client.interface_name = payload.interface_name
        client.last_seen = now

    await session.commit()
    return ClientRegistrationResponse(
        client_id=payload.client_id,
        accepted=True,
        metrics_interval_seconds=settings.metrics_interval_seconds,
        udp_echo_host=settings.public_base_url.split("://", maxsplit=1)[-1].split(":")[0],
        udp_echo_port=settings.udp_echo_port,
    )


@router.get("/", response_model=list[ClientListItem])
async def list_clients(
    session: AsyncSession = Depends(get_session),
) -> list[ClientListItem]:
    clients = list(
        (
            await session.scalars(
                select(ClientRecord).order_by(
                    desc(ClientRecord.last_seen),
                    ClientRecord.hostname.asc(),
                )
            )
        ).all()
    )
    metrics = await latest_metric_map(session, [client.client_id for client in clients])
    items: list[ClientListItem] = []
    for client in clients:
        latest_metric = metrics.get(client.client_id)
        online = is_online(client.last_seen)
        health = "offline" if not online else client.last_status
        items.append(
            ClientListItem(
                client_id=client.client_id,
                hostname=client.hostname,
                username=client.username,
                os=client.os,
                client_version=client.client_version,
                local_ip=client.local_ip,
                interface_name=client.interface_name,
                online=online,
                last_seen=client.last_seen,
                latency_ms=latest_metric.latency_ms if latest_metric else None,
                jitter_ms=latest_metric.jitter_ms if latest_metric else None,
                packet_loss_percent=latest_metric.packet_loss_percent if latest_metric else None,
                tx_mbps=latest_metric.tx_mbps if latest_metric else None,
                rx_mbps=latest_metric.rx_mbps if latest_metric else None,
                health=health,
            )
        )
    return items


@router.get("/{client_id}")
async def get_client(
    client_id: UUID,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    limit: int = Query(default=300, ge=1, le=2000),
    session: AsyncSession = Depends(get_session),
) -> dict:
    client = await session.get(ClientRecord, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    metrics_query: Select[tuple[ClientMetricRecord]] = (
        select(ClientMetricRecord)
        .where(ClientMetricRecord.client_id == client_id)
        .order_by(ClientMetricRecord.ts.desc())
        .limit(limit)
    )
    if from_ is not None:
        metrics_query = metrics_query.where(ClientMetricRecord.ts >= from_)
    if to is not None:
        metrics_query = metrics_query.where(ClientMetricRecord.ts <= to)

    metrics = list((await session.scalars(metrics_query)).all())
    metrics.reverse()
    events = list(
        (
            await session.scalars(
                select(EventRecord)
                .where(EventRecord.client_id == client_id)
                .order_by(EventRecord.ts.desc())
                .limit(20)
            )
        ).all()
    )

    online = is_online(client.last_seen)
    metadata = ClientMetadata(
        client_id=client.client_id,
        hostname=client.hostname,
        username=client.username,
        os=client.os,
        client_version=client.client_version,
        local_ip=client.local_ip,
        interface_name=client.interface_name,
        last_seen=client.last_seen,
        first_seen=client.first_seen,
        online=online,
        health="offline" if not online else client.last_status,
    )
    return {
        "client": metadata.model_dump(mode="json"),
        "metrics": [
            ClientMetricPoint(
                timestamp=metric.ts,
                latency_ms=metric.latency_ms,
                jitter_ms=metric.jitter_ms,
                packet_loss_percent=metric.packet_loss_percent,
                tx_mbps=metric.tx_mbps,
                rx_mbps=metric.rx_mbps,
                server_reachable=metric.server_reachable,
            ).model_dump(mode="json")
            for metric in metrics
        ],
        "events": [
            EventView(
                id=event.id,
                ts=event.ts,
                severity=event.severity,
                client_id=event.client_id,
                event_type=event.event_type,
                message=event.message,
                data=event.data,
            ).model_dump(mode="json")
            for event in events
        ],
        "last_metrics_payload": client.last_metrics_payload,
    }
