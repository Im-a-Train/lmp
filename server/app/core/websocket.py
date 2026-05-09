from __future__ import annotations

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_json(self, message: dict) -> None:
        stale_connections: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                stale_connections.append(connection)
            except RuntimeError:
                stale_connections.append(connection)
        for connection in stale_connections:
            self.disconnect(connection)


manager = ConnectionManager()
