"""Preservation and safety checks specific to migration 0003.

These tests deliberately construct 0002-shaped rows with raw SQL.  That
exercises the SQLite batch recreation path against the foreign keys that
already existed before Phase 3B, without using a school database or data.
"""

from __future__ import annotations

from alembic import command
from alembic.config import Config
from alembic import op
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.database import create_database_engine


BATCH_ID = "00000000-0000-0000-0000-000000000301"


def _config_at_0002(tmp_path, monkeypatch) -> tuple[Config, object]:
    url = f"sqlite:///{(tmp_path / 'migration-3b.db').as_posix()}"
    monkeypatch.setenv("CONTROL_ESTUDIANTIL_DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0002_import_preview")
    return config, create_database_engine(Settings(url, ()))


def _seed_0002_rows(engine) -> None:
    """Seed every pre-0003 source_batch foreign key plus a preview row."""
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE departments SET availability='NO_DISPONIBLE' WHERE id=1")
        )
        connection.execute(
            text(
                "INSERT INTO import_batches "
                "(id, profile, file_hash, scope, status, created_at, expires_at, proposal) "
                "VALUES (:id, 'synthetic', :hash, 'SUBCONJUNTO', 'PREVIEW', "
                "'2026-09-10 10:00:00', '2026-09-11 10:00:00', '{}')"
            ),
            {"id": BATCH_ID, "hash": "0" * 64},
        )
        connection.execute(
            text(
                "INSERT INTO import_rows (batch_id, row_number, category, payload) "
                "VALUES (:id, 8, 'NUEVO', '{}')"
            ),
            {"id": BATCH_ID},
        )
        connection.execute(
            text(
                "INSERT INTO academic_periods (id, label, period_key) "
                "VALUES (1, '2026-2027', '2026-2027')"
            )
        )
        connection.execute(
            text("INSERT INTO institution (id, name, active_academic_period_id) VALUES (1, 'Institución sintética', 1)")
        )
        connection.execute(
            text(
                "INSERT INTO students "
                "(id, first_name, last_name, active, created_at, updated_at, source_batch_id, source_baseline) "
                "VALUES (1, 'Ana', 'Prueba', 1, '2026-09-10 10:00:00', "
                "'2026-09-10 10:00:00', :id, '{}')"
            ),
            {"id": BATCH_ID},
        )
        connection.execute(
            text(
                "INSERT INTO student_academic_placements "
                "(id, student_id, academic_period_id, course, parallel, recorded_from, source_batch_id) "
                "VALUES (1, 1, 1, 'Octavo', 'A', '2026-09-10 10:00:00', :id)"
            ),
            {"id": BATCH_ID},
        )
        connection.execute(
            text(
                "INSERT INTO student_contacts "
                "(id, student_id, type, active, updated_at, source_batch_id, source_baseline) "
                "VALUES (1, 1, 'EMERGENCIA', 1, '2026-09-10 10:00:00', :id, '{}')"
            ),
            {"id": BATCH_ID},
        )


def _assert_seed_preserved(engine) -> None:
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT availability FROM departments WHERE id=1")) == "NO_DISPONIBLE"
        assert connection.scalar(text("SELECT count(*) FROM import_rows WHERE batch_id=:id"), {"id": BATCH_ID}) == 1
        assert connection.scalar(text("SELECT source_batch_id FROM students WHERE id=1")) == BATCH_ID
        assert connection.scalar(text("SELECT source_batch_id FROM student_contacts WHERE id=1")) == BATCH_ID
        assert connection.scalar(text("SELECT source_batch_id FROM student_academic_placements WHERE id=1")) == BATCH_ID
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []


def test_0003_preserves_0002_previews_departments_and_source_batch_foreign_keys(tmp_path, monkeypatch):
    config, engine = _config_at_0002(tmp_path, monkeypatch)
    try:
        _seed_0002_rows(engine)
        command.upgrade(config, "0003_import_apply")
        _assert_seed_preserved(engine)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT application_contract_version FROM import_batches WHERE id=:id"), {"id": BATCH_ID}) is None
            assert connection.scalar(text("SELECT manual_protected_fields FROM students WHERE id=1")) is None
            assert connection.scalar(text("SELECT source_baseline FROM student_academic_placements WHERE id=1")) is None
            assert connection.scalar(text("SELECT manual_protected_fields FROM student_contacts WHERE id=1")) is None
    finally:
        engine.dispose()


def test_0003_application_state_constraint_and_applied_downgrade_protection(tmp_path, monkeypatch):
    config, engine = _config_at_0002(tmp_path, monkeypatch)
    try:
        _seed_0002_rows(engine)
        command.upgrade(config, "0003_import_apply")
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(text("UPDATE import_batches SET status='APPLIED' WHERE id=:id"), {"id": BATCH_ID})
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE import_batches SET status='APPLIED', applied_at='2026-09-10 11:00:00', "
                    "applied_result='{}' WHERE id=:id"
                ),
                {"id": BATCH_ID},
            )
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(text("UPDATE import_batches SET status='PREVIEW' WHERE id=:id"), {"id": BATCH_ID})
        with pytest.raises(RuntimeError, match="No se puede revertir 0003"):
            command.downgrade(config, "0002_import_preview")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0003_import_apply"
            assert connection.scalar(text("SELECT status FROM import_batches WHERE id=:id"), {"id": BATCH_ID}) == "APPLIED"
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
    finally:
        engine.dispose()


def test_0003_downgrade_then_upgrade_preserves_non_applied_preview(tmp_path, monkeypatch):
    config, engine = _config_at_0002(tmp_path, monkeypatch)
    try:
        _seed_0002_rows(engine)
        command.upgrade(config, "0003_import_apply")
        command.downgrade(config, "0002_import_preview")
        _assert_seed_preserved(engine)
        with engine.connect() as connection:
            columns = {column["name"] for column in connection.dialect.get_columns(connection, "import_batches")}
            assert "applied_result" not in columns
        command.upgrade(config, "0003_import_apply")
        _assert_seed_preserved(engine)
    finally:
        engine.dispose()


def test_0003_failure_during_batch_recreation_rolls_back_and_restores_foreign_keys(tmp_path, monkeypatch):
    """An interrupted reconstruction leaves the valid 0002 schema intact."""
    config, engine = _config_at_0002(tmp_path, monkeypatch)
    try:
        _seed_0002_rows(engine)
        original_batch_alter_table = op.batch_alter_table

        def fail_before_students(table_name, *args, **kwargs):
            if table_name == "students":
                raise RuntimeError("simulated 0003 batch failure")
            return original_batch_alter_table(table_name, *args, **kwargs)

        monkeypatch.setattr(op, "batch_alter_table", fail_before_students)
        with pytest.raises(RuntimeError, match="simulated 0003 batch failure"):
            command.upgrade(config, "0003_import_apply")
        _assert_seed_preserved(engine)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002_import_preview"
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
            columns = {column["name"] for column in connection.dialect.get_columns(connection, "import_batches")}
            assert "applied_result" not in columns
    finally:
        engine.dispose()
