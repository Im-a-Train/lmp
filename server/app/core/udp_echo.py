from __future__ import annotations

import asyncio


class UdpEchoProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.transport.sendto(data, addr)


async def start_udp_echo_server(host: str, port: int) -> asyncio.transports.DatagramTransport:
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: UdpEchoProtocol(),
        local_addr=(host, port),
    )
    return transport
