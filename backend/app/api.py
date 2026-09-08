"""Rutas HTTP disponibles durante la Fase 1."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Indica que el proceso backend está operativo."""
    return {"status": "ok"}
