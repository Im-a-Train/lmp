from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.event import EventRecord, EventView

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/", response_model=list[EventView])
async def list_events(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[EventView]:
    events = list((await session.scalars(select(EventRecord).order_by(EventRecord.ts.desc()).limit(limit))).all())
    return [
        EventView(
            id=event.id,
            ts=event.ts,
            severity=event.severity,
            client_id=event.client_id,
            event_type=event.event_type,
            message=event.message,
            data=event.data,
        )
        for event in events
    ]
