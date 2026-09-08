"""Configuración mínima del backend leída desde variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CORS_ORIGINS = ("http://localhost:4200", "http://127.0.0.1:4200")


@dataclass(frozen=True)
class Settings:
    database_url: str
    cors_origins: tuple[str, ...]


def get_settings() -> Settings:
    project_directory = Path(__file__).resolve().parent.parent
    default_database = project_directory / "data" / "control_estudiantil.db"
    database_url = os.getenv(
        "CONTROL_ESTUDIANTIL_DATABASE_URL", f"sqlite:///{default_database.as_posix()}"
    )
    origins_value = os.getenv("CONTROL_ESTUDIANTIL_CORS_ORIGINS")
    origins = (
        tuple(origin.strip() for origin in origins_value.split(",") if origin.strip())
        if origins_value
        else DEFAULT_CORS_ORIGINS
    )
    return Settings(database_url=database_url, cors_origins=origins)
