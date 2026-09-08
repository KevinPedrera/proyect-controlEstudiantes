"""Infraestructura WebSocket sin eventos de negocio."""

from __future__ import annotations

from fastapi import WebSocket


class ConnectionManager:
    """Mantiene las conexiones activas para los avisos de fases posteriores."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)


async def websocket_endpoint(websocket: WebSocket) -> None:
    """Acepta conexiones y libera el cliente cuando este se desconecta."""
    manager: ConnectionManager = websocket.app.state.connection_manager
    await manager.connect(websocket)
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    finally:
        manager.disconnect(websocket)
