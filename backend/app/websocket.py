"""Conexiones WebSocket y avisos transitorios de departamentos."""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Mantiene conexiones y aísla fallos de difusión después del commit."""

    def __init__(self) -> None:
        self._connections: dict[WebSocket, asyncio.Lock] = {}

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        lock = asyncio.Lock()
        # Register before the handshake becomes visible; broadcasters wait until
        # accept finishes, so a reconnect followed by GET cannot miss a change.
        async with lock:
            self._connections[websocket] = lock
            try:
                await asyncio.wait_for(websocket.accept(), timeout=2)
            except BaseException:
                self.disconnect(websocket)
                raise

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.pop(websocket, None)

    async def departments_changed(self) -> None:
        await asyncio.gather(*(
            self._notify(websocket, lock)
            for websocket, lock in list(self._connections.items())
        ))

    async def _notify(self, websocket: WebSocket, lock: asyncio.Lock) -> None:
        try:
            async with asyncio.timeout(2):
                async with lock:
                    if websocket in self._connections:
                        await websocket.send_json({"type": "departments_changed"})
        except Exception:
            self.disconnect(websocket)
            logger.warning("Se cerrará una conexión WebSocket cuyo aviso falló.")
            try:
                await asyncio.wait_for(websocket.close(code=1011), timeout=1)
            except Exception:
                pass


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
