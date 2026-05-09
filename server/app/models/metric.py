from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ClientMetricRecord(Base):
    __tablename__ = "client_metrics"
    __table_args__ = (
        Index("idx_client_metrics_ts", "ts"),
        Index("idx_client_metrics_client_ts", "client_id", "ts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("clients.client_id", ondelete="CASCADE"),
        nullable=False,
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    jitter_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    packet_loss_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    tx_mbps: Mapped[float | None] = mapped_column(Float, nullable=True)
    rx_mbps: Mapped[float | None] = mapped_column(Float, nullable=True)
    server_reachable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    game_server_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    game_server_packet_loss_percent: Mapped[float | None] = mapped_column(Float, nullable=True)

    client = relationship("ClientRecord", back_populates="metrics")


class ClientMetricIn(BaseModel):
    client_id: UUID
    timestamp: datetime
    latency_ms: float | None = None
    jitter_ms: float | None = None
    packet_loss_percent: float | None = None
    tx_mbps: float | None = None
    rx_mbps: float | None = None
    server_reachable: bool = True
    game_server_latency_ms: float | None = None
    game_server_packet_loss_percent: float | None = None
    local_ip: str | None = None
    interface_name: str | None = None


class ClientMetricPoint(BaseModel):
    timestamp: datetime
    latency_ms: float | None = None
    jitter_ms: float | None = None
    packet_loss_percent: float | None = None
    tx_mbps: float | None = None
    rx_mbps: float | None = None
    server_reachable: bool


class DashboardSummary(BaseModel):
    online_clients: int
    offline_clients: int
    global_health: str
    worst_latency_clients: list[dict]
    packet_loss_alerts: list[dict]
    jitter_alerts: list[dict]
    top_bandwidth_users: list[dict]
