from __future__ import annotations

from dataclasses import dataclass


HEALTH_ORDER = {"green": 0, "yellow": 1, "red": 2, "offline": 3, "unknown": 4}


@dataclass(slots=True)
class MetricSnapshot:
    latency_ms: float | None
    jitter_ms: float | None
    packet_loss_percent: float | None


def classify_latency(latency_ms: float | None) -> str:
    if latency_ms is None:
        return "unknown"
    if latency_ms <= 5:
        return "green"
    if latency_ms <= 20:
        return "yellow"
    return "red"


def classify_jitter(jitter_ms: float | None) -> str:
    if jitter_ms is None:
        return "unknown"
    if jitter_ms <= 2:
        return "green"
    if jitter_ms <= 10:
        return "yellow"
    return "red"


def classify_packet_loss(packet_loss_percent: float | None) -> str:
    if packet_loss_percent is None:
        return "unknown"
    if packet_loss_percent <= 0:
        return "green"
    if packet_loss_percent <= 1:
        return "yellow"
    return "red"


def worst_health(*statuses: str) -> str:
    non_unknown = [status for status in statuses if status != "unknown"]
    if not non_unknown:
        return "unknown"
    return max(non_unknown, key=lambda status: HEALTH_ORDER[status])


def classify_client_health(snapshot: MetricSnapshot) -> str:
    return worst_health(
        classify_latency(snapshot.latency_ms),
        classify_jitter(snapshot.jitter_ms),
        classify_packet_loss(snapshot.packet_loss_percent),
    )


def classify_global_health(client_statuses: list[str], offline_ratio: float) -> str:
    active = [status for status in client_statuses if status not in {"offline", "unknown"}]
    if not active:
        return "unknown"
    global_status = worst_health(*active)
    if offline_ratio > 0.2 and global_status == "green":
        return "yellow"
    return global_status
