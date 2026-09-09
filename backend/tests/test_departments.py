from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from app.main import create_app

EXPECTED = [
    ("Inspección General", "INSPECCION"),
    ("Inspección Primaria", "INSPECCION"),
    ("Inspección Bachillerato", "INSPECCION"),
    ("DECE Primaria", "DECE"),
    ("DECE Secundaria/Bachillerato", "DECE"),
    ("Psicopedagogía", "DECE"),
    ("Departamento Médico", "SALUD"),
    ("Departamento Odontológico", "SALUD"),
]


def put(client, value, department_id=1):
    return client.put(f"/api/departments/{department_id}/availability", json={"availability": value})


def test_catalogue_contract_defaults_and_order(client):
    response = client.get("/api/departments")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    rows = response.json()
    assert [(row["name"], row["group"]) for row in rows] == EXPECTED
    assert len({row["id"] for row in rows}) == 8
    assert all(row["active"] is True and row["availability"] == "DISPONIBLE" for row in rows)
    assert all(set(row) == {"id", "name", "group", "active", "availability"} for row in rows)


def test_changes_are_persistent_and_reversible(client):
    assert put(client, "NO_DISPONIBLE").json()["availability"] == "NO_DISPONIBLE"
    with TestClient(create_app(client.app.state.settings)) as restarted:
        assert restarted.get("/api/departments").json()[0]["availability"] == "NO_DISPONIBLE"
        assert put(restarted, "DISPONIBLE").json()["availability"] == "DISPONIBLE"


def test_idempotent_request_performs_no_update_or_notification(client, monkeypatch):
    notify = AsyncMock()
    monkeypatch.setattr(client.app.state.connection_manager, "departments_changed", notify)
    statements = []
    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(client.app.state.engine, "before_cursor_execute", record)
    assert put(client, "DISPONIBLE").status_code == 200
    assert not any(sql.lstrip().upper().startswith("UPDATE") for sql in statements)
    notify.assert_not_called()


def test_not_found_and_inactive(client, monkeypatch):
    notify = AsyncMock()
    monkeypatch.setattr(client.app.state.connection_manager, "departments_changed", notify)
    assert put(client, "NO_DISPONIBLE", 999).status_code == 404
    with client.app.state.engine.begin() as connection:
        connection.execute(text("UPDATE departments SET active=0 WHERE id=1"))
    assert put(client, "NO_DISPONIBLE").status_code == 409
    row = client.get("/api/departments").json()[0]
    assert row["active"] is False and row["availability"] == "DISPONIBLE"
    notify.assert_not_called()


@pytest.mark.parametrize("body", [{}, {"availability": "OCUPADO"}, {"availability": None}, {"availability": True}, {"availability": "DISPONIBLE", "active": False}])
def test_invalid_body(client, body):
    assert client.put("/api/departments/1/availability", json=body).status_code == 422


@pytest.mark.parametrize("identifier", ["0", "-1", "abc", "1.5"])
def test_invalid_id(client, identifier):
    assert put(client, "DISPONIBLE", identifier).status_code == 422


@pytest.mark.parametrize("assignment", [
    "\"group\"='OTHER'", "availability='OCUPADO'", "active=2", "name=''",
    "name=' space '", "name=NULL", "\"group\"=NULL", "active=NULL", "availability=NULL",
    "name='Inspección Primaria'", "name='" + "a" * 121 + "'",
])
def test_database_constraints(client, assignment):
    with pytest.raises(IntegrityError):
        with client.app.state.engine.begin() as connection:
            connection.execute(text(f"UPDATE departments SET {assignment} WHERE id=1"))


def test_two_websocket_clients_receive_after_commit(client):
    with client.websocket_connect("/ws") as first, client.websocket_connect("/ws") as second:
        assert put(client, "NO_DISPONIBLE").status_code == 200
        assert first.receive_json() == {"type": "departments_changed"}
        assert second.receive_json() == {"type": "departments_changed"}
        with client.app.state.engine.connect() as connection:
            assert connection.scalar(text("SELECT availability FROM departments WHERE id=1")) == "NO_DISPONIBLE"


def test_notification_observes_committed_state(client, monkeypatch):
    async def verify_commit():
        with client.app.state.engine.connect() as connection:
            assert connection.scalar(text("SELECT availability FROM departments WHERE id=1")) == "NO_DISPONIBLE"
    monkeypatch.setattr(client.app.state.connection_manager, "departments_changed", verify_commit)
    assert put(client, "NO_DISPONIBLE").status_code == 200


def test_failed_client_does_not_undo_commit_or_break_other_clients(client):
    broken = AsyncMock()
    broken.send_json.side_effect = RuntimeError("disconnected")
    manager = client.app.state.connection_manager
    client.portal.call(manager.connect, broken)
    with client.websocket_connect("/ws") as healthy:
        assert put(client, "NO_DISPONIBLE").status_code == 200
        assert healthy.receive_json() == {"type": "departments_changed"}
        assert manager.connection_count == 1
    broken.close.assert_awaited_once()


@pytest.mark.parametrize("values", [("NO_DISPONIBLE", "NO_DISPONIBLE"), ("NO_DISPONIBLE", "DISPONIBLE")])
def test_concurrent_assignments_use_independent_connections(client, values):
    barrier = Barrier(2)
    commits = []
    engine = client.app.state.engine
    def committed(connection):
        if connection.get_execution_options().get("sqlite_write"):
            commits.append(connection.scalar(text("SELECT availability FROM departments WHERE id=1")))
    event.listen(engine, "commit", committed)
    def write(value):
        with TestClient(client.app) as independent:
            barrier.wait(timeout=5)
            return put(independent, value)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, values))
    assert all(result.status_code == 200 for result in results)
    assert len(commits) == 2
    assert client.get("/api/departments").json()[0]["availability"] == commits[-1]


def test_put_cors_preflight(client):
    response = client.options("/api/departments/1/availability", headers={
        "Origin": "http://localhost:4200", "Access-Control-Request-Method": "PUT",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200


def test_rollback_does_not_notify_or_change_state(client, monkeypatch):
    notify = AsyncMock()
    monkeypatch.setattr(client.app.state.connection_manager, "departments_changed", notify)
    def fail_commit(connection):
        raise RuntimeError("simulated commit failure")
    engine = client.app.state.engine
    event.listen(engine, "commit", fail_commit)
    try:
        assert put(client, "NO_DISPONIBLE").status_code == 500
    finally:
        event.remove(engine, "commit", fail_commit)
    assert client.get("/api/departments").json()[0]["availability"] == "DISPONIBLE"
    notify.assert_not_called()
