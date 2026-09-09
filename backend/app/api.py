"""Salud del proceso y contratos HTTP de departamentos."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request, Response
from sqlalchemy.exc import OperationalError
from starlette.concurrency import run_in_threadpool

from app.departments import DepartmentInactive, DepartmentNotFound, list_departments, set_availability
from app.schemas import AvailabilityUpdate, DepartmentResponse

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Indica que el proceso backend está operativo."""
    return {"status": "ok"}


@router.get("/departments", response_model=list[DepartmentResponse])
def departments(request: Request, response: Response) -> list[DepartmentResponse]:
    response.headers["Cache-Control"] = "no-store"
    return list_departments(request.app.state.session_factory)


@router.put("/departments/{department_id}/availability", response_model=DepartmentResponse)
async def update_availability(
    department_id: Annotated[int, Path(gt=0)],
    body: AvailabilityUpdate,
    request: Request,
    response: Response,
) -> DepartmentResponse:
    try:
        result, changed = await run_in_threadpool(
            set_availability, request.app.state.session_factory, department_id, body.availability
        )
    except DepartmentNotFound:
        raise HTTPException(404, "Departamento no encontrado.") from None
    except DepartmentInactive:
        raise HTTPException(409, "El departamento está inactivo.") from None
    except OperationalError as error:
        code = getattr(error.orig, "sqlite_errorcode", 0)
        if code & 0xFF in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
            raise HTTPException(503, "Base de datos ocupada. Intente nuevamente.") from None
        raise
    response.headers["Cache-Control"] = "no-store"
    if changed:
        await request.app.state.connection_manager.departments_changed()
    return result
