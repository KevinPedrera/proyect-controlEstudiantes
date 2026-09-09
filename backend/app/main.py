"""Punto de entrada de FastAPI."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.import_api import ImportBodyLimit, router as import_router, start_cleanup, stop_cleanup
from app.config import Settings, get_settings
from app.database import create_database_engine, create_session_factory
from app.websocket import ConnectionManager, websocket_endpoint

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Libera los recursos del motor cuando el proceso termina."""
    cleanup_task = await start_cleanup(app)
    try:
        yield
    finally:
        await stop_cleanup(cleanup_task)
        app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construye la aplicación sin inicializar recursos de dominio."""
    resolved_settings = settings or get_settings()
    app = FastAPI(
        title="Control Estudiantil",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.engine = create_database_engine(resolved_settings)
    app.state.session_factory = create_session_factory(app.state.engine)
    app.state.connection_manager = ConnectionManager()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "PUT", "POST"],
        allow_headers=[],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Error no controlado en la API", exc_info=exc)
        return JSONResponse(
            status_code=500, content={"detail": "Error interno del servidor."}
        )

    app.include_router(api_router, prefix="/api")
    app.include_router(import_router, prefix="/api")
    app.add_middleware(ImportBodyLimit)
    app.add_api_websocket_route("/ws", websocket_endpoint)
    return app


app = create_app()
