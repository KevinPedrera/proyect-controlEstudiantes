from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from app.config import get_settings
from app.database import create_database_engine, metadata
from app import models  # noqa: F401 -- register tables with metadata
from app import student_models  # noqa: F401 -- register phase 3A tables

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option(
    "sqlalchemy.url", get_settings().database_url.replace("%", "%%")
)
target_metadata = metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        transactional_ddl=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_database_engine(get_settings())
    with connectable.connect() as connection:
        # Revision 0003 reconstructs a SQLite table referenced by preview rows and
        # accepted records.  SQLite only permits that reconstruction with FK checks
        # disabled before the migration transaction begins; integrity is checked
        # before re-enabling them.
        driver = connection.connection.driver_connection
        driver.execute("PRAGMA foreign_keys=OFF")
        try:
            context.configure(connection=connection, target_metadata=target_metadata, transactional_ddl=True)
            with context.begin_transaction():
                context.run_migrations()
                if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
                    raise RuntimeError("La migración dejó claves foráneas inválidas.")
        finally:
            # Also restores enforcement after a failed migration/rollback.
            if connection.in_transaction():
                connection.rollback()
            driver.execute("PRAGMA foreign_keys=ON")
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
