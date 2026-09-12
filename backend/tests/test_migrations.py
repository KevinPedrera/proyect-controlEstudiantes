from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
import pytest

from app.config import Settings
from app.database import create_database_engine


def test_upgrade_downgrade_upgrade_and_check(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("CONTROL_ESTUDIANTIL_DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0001_departments")
    engine = create_database_engine(Settings(url, ()))
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT count(*) FROM departments")) == 8
        connection.execute(text("UPDATE departments SET availability='NO_DISPONIBLE' WHERE id=1"))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM departments")) == 8
        assert connection.scalar(text("SELECT availability FROM departments WHERE id=1")) == "NO_DISPONIBLE"
    command.current(config)
    command.heads(config)
    command.check(config)
    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    command.upgrade(config, "head")
    assert set(inspect(engine).get_table_names()) == {"alembic_version", "movements", "departments", "institution", "academic_periods", "students", "student_academic_placements", "student_contacts", "import_batches", "import_rows"}
    command.check(config)
    engine.dispose()


def test_failed_seed_rolls_back_schema_and_can_be_retried(tmp_path, monkeypatch):
    from alembic import op

    url = f"sqlite:///{(tmp_path / 'failed-migration.db').as_posix()}"
    monkeypatch.setenv("CONTROL_ESTUDIANTIL_DATABASE_URL", url)
    config = Config("alembic.ini")
    def fail_seed(*args, **kwargs):
        raise RuntimeError("simulated seed failure")
    with monkeypatch.context() as context:
        context.setattr(op, "bulk_insert", fail_seed)
        with pytest.raises(RuntimeError, match="simulated seed failure"):
            command.upgrade(config, "head")
    engine = create_database_engine(Settings(url, ()))
    assert "departments" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM departments")) == 8
    engine.dispose()
