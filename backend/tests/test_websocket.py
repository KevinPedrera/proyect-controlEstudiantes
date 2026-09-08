def test_websocket_registers_binary_clients_and_releases_them(client) -> None:
    manager = client.app.state.connection_manager
    assert manager.connection_count == 0

    with client.websocket_connect("/ws") as first_client:
        assert manager.connection_count == 1
        first_client.send_bytes(b"binary-frame")

        with client.websocket_connect("/ws") as second_client:
            assert manager.connection_count == 2

        assert manager.connection_count == 1

    assert manager.connection_count == 0
