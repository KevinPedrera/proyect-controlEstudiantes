from sqlalchemy import text

from app.config import Settings
from app.database import create_database_engine


def test_sqlite_foreign_keys_are_enabled_for_each_connection(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{(tmp_path / 'foreign_keys.db').as_posix()}",
        cors_origins=("http://localhost:4200",),
    )
    engine = create_database_engine(settings)

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1

    engine.dispose()


def test_non_sqlite_database_urls_are_rejected() -> None:
    settings = Settings(
        database_url="postgresql://localhost/control_estudiantil",
        cors_origins=("http://localhost:4200",),
    )

    try:
        create_database_engine(settings)
    except ValueError as error:
        assert str(error) == "La base de datos configurada debe usar SQLite."
    else:
        raise AssertionError("Se esperaba rechazar una URL que no usa SQLite.")


def test_unknown_sqlite_like_backend_is_rejected() -> None:
    settings = Settings(
        database_url="sqlitefake:///control_estudiantil.db",
        cors_origins=("http://localhost:4200",),
    )

    try:
        create_database_engine(settings)
    except ValueError as error:
        assert str(error) == "La base de datos configurada debe usar SQLite."
    else:
        raise AssertionError("Se esperaba rechazar un backend SQLite no válido.")
