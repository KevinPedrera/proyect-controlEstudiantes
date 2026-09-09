from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        cors_origins=("http://localhost:4200",),
    )
    monkeypatch.setenv("CONTROL_ESTUDIANTIL_DATABASE_URL", settings.database_url)
    command.upgrade(Config("alembic.ini"), "head")
    with TestClient(create_app(settings), raise_server_exceptions=False) as test_client:
        yield test_client
