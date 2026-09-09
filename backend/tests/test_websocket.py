import asyncio
from unittest.mock import AsyncMock

from app.websocket import ConnectionManager


def test_websocket_registers_binary_clients_and_releases_them(client) -> None:
    manager = client.app.state.connection_manager
    assert manager.connection_count == 0

    with client.websocket_connect("/ws") as first_client:
        assert manager.connection_count == 1
        first_client.send_bytes(b"binary-frame")

        with client.websocket_connect("/ws"):
            assert manager.connection_count == 2

        assert manager.connection_count == 1

    assert manager.connection_count == 0


def test_register_before_handshake_and_wait_before_sending():
    async def scenario():
        manager = ConnectionManager()
        accepting = asyncio.Event()
        finish_accept = asyncio.Event()
        socket = AsyncMock()
        async def accept():
            accepting.set()
            await finish_accept.wait()
        socket.accept.side_effect = accept
        connect = asyncio.create_task(manager.connect(socket))
        await accepting.wait()
        assert manager.connection_count == 1
        broadcast = asyncio.create_task(manager.departments_changed())
        await asyncio.sleep(0)
        socket.send_json.assert_not_called()
        finish_accept.set()
        await connect
        await broadcast
        socket.send_json.assert_awaited_once_with({"type": "departments_changed"})
    asyncio.run(scenario())


def test_slow_client_is_removed_without_blocking_healthy_client():
    async def scenario():
        manager = ConnectionManager()
        slow = AsyncMock()
        healthy = AsyncMock()
        async def never_receive(*args):
            await asyncio.Event().wait()
        slow.send_json.side_effect = never_receive
        await manager.connect(slow)
        await manager.connect(healthy)
        await asyncio.wait_for(manager.departments_changed(), timeout=4)
        assert manager.connection_count == 1
        slow.close.assert_awaited_once_with(code=1011)
        healthy.send_json.assert_awaited_once_with({"type": "departments_changed"})
    asyncio.run(scenario())
