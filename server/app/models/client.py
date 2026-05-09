from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ClientRecord(Base):
    __tablename__ = "clients"

    client_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    hostname: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    os: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    local_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    interface_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_status: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    last_metrics_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    metrics = relationship("ClientMetricRecord", back_populates="client", cascade="all, delete-orphan")
    events = relationship("EventRecord", back_populates="client")


class ClientRegistrationRequest(BaseModel):
    client_id: UUID
    hostname: str
    username: str | None = None
    os: str | None = None
    client_version: str | None = None
    local_ip: str | None = None
    interface_name: str | None = None


class ClientRegistrationResponse(BaseModel):
    client_id: UUID
    accepted: bool
    metrics_interval_seconds: int
    udp_echo_host: str
    udp_echo_port: int


class ClientListItem(BaseModel):
    client_id: UUID
    hostname: str
    username: str | None = None
    os: str | None = None
    client_version: str | None = None
    local_ip: str | None = None
    interface_name: str | None = None
    online: bool
    last_seen: datetime
    latency_ms: float | None = None
    jitter_ms: float | None = None
    packet_loss_percent: float | None = None
    tx_mbps: float | None = None
    rx_mbps: float | None = None
    health: str


class ClientSummary(BaseModel):
    client_id: UUID
    hostname: str
    username: str | None = None
    local_ip: str | None = None
    health: str
    latency_ms: float | None = None
    jitter_ms: float | None = None
    packet_loss_percent: float | None = None
    tx_mbps: float | None = None
    rx_mbps: float | None = None


class ClientMetadata(BaseModel):
    client_id: UUID
    hostname: str
    username: str | None = None
    os: str | None = None
    client_version: str | None = None
    local_ip: str | None = None
    interface_name: str | None = None
    last_seen: datetime
    first_seen: datetime
    online: bool
    health: str
