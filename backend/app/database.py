"""Conexión SQLite exclusiva del backend y control de transacciones."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker

from app.config import Settings

metadata = MetaData()


def create_database_engine(settings: Settings) -> Engine:
    """Crea el motor SQLite y habilita sus claves foráneas por conexión."""
    database_url = make_url(settings.database_url)
    if database_url.get_backend_name() != "sqlite":
        raise ValueError("La base de datos configurada debe usar SQLite.")

    database_path = database_url.database
    if database_path and database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        settings.database_url,
        hide_parameters=True,
        connect_args={"check_same_thread": False, "timeout": 5},
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
        # SQLAlchemy controls BEGIN, including transactional migration DDL.
        dbapi_connection.isolation_level = None  # type: ignore[attr-defined]
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA secure_delete=ON")
        cursor.close()

    @event.listens_for(engine, "begin")
    def begin_transaction(connection) -> None:
        statement = (
            "BEGIN IMMEDIATE"
            if connection.get_execution_options().get("sqlite_write")
            else "BEGIN"
        )
        connection.exec_driver_sql(statement)

    return engine


def create_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)
