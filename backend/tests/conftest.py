from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        cors_origins=("http://localhost:4200",),
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as test_client:
        yield test_client
