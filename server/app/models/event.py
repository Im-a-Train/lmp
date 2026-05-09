from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EventRecord(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("idx_events_ts", "ts"),
        Index("idx_events_client_ts", "client_id", "ts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    client_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("clients.client_id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    client = relationship("ClientRecord", back_populates="events")


class EventView(BaseModel):
    id: int
    ts: datetime
    severity: str
    client_id: UUID | None = None
    event_type: str
    message: str
    data: dict | None = None
