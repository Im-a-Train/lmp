from __future__ import annotations

import asyncio
import socket

from zeroconf import ServiceInfo, Zeroconf

_SERVICE_TYPE = "_lpm._tcp.local."


def _lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


async def start_mdns(app_name: str, port: int) -> tuple[Zeroconf, ServiceInfo]:
    ip = _lan_ip()
    hostname = socket.gethostname()
    service_name = f"{app_name}.{_SERVICE_TYPE}"

    info = ServiceInfo(
        _SERVICE_TYPE,
        service_name,
        addresses=[socket.inet_aton(ip)],
        port=port,
        properties={"version": "0.1.0"},
        server=f"{hostname}.local.",
    )
    zc = Zeroconf()
    await asyncio.to_thread(zc.register_service, info)
    return zc, info


async def stop_mdns(zc: Zeroconf, info: ServiceInfo) -> None:
    await asyncio.to_thread(zc.unregister_service, info)
    await asyncio.to_thread(zc.close)
