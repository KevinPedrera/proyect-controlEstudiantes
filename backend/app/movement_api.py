"""Minimal operational API; domain failures never expose database details."""
import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.concurrency import run_in_threadpool

from app import movements

router = APIRouter()
logger = logging.getLogger(__name__)
Identifier = Annotated[int, Field(strict=True, gt=0)]


class DirectRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    student_id: Identifier
    destination_department_id: Identifier


class SendRequest(DirectRequest):
    origin_department_id: Identifier | None = None


async def execute(request, response, operation, *args, write=False):
    response.headers['Cache-Control'] = 'no-store'
    try:
        result = await run_in_threadpool(operation, request.app.state.session_factory, *args)
    except movements.MovementError as error:
        raise HTTPException(error.status, error.detail) from None
    except IntegrityError:
        raise HTTPException(409, dict(code='CONFLICTO_CONCURRENTE', message='No se pudo aplicar la acción. Consulta el estado actualizado.')) from None
    except OperationalError:
        raise HTTPException(503, dict(code='BASE_NO_DISPONIBLE', message='No se pudo confirmar la operación. Actualiza el estado antes de reintentar.')) from None
    except Exception:
        logger.error('Falló una operación de movimientos; no se registran datos personales.')
        raise HTTPException(500, dict(code='ERROR_MOVIMIENTO', message='No se pudo confirmar la operación. Consulta el estado actualizado.')) from None
    if write:
        result, changed = result
        if changed:
            await request.app.state.connection_manager.movements_changed()
    return result


@router.post('/movements', status_code=201)
async def send(body: SendRequest, request: Request, response: Response):
    return await execute(request, response, movements.create_movement, body.student_id,
                         body.destination_department_id, body.origin_department_id, write=True)


@router.post('/movements/direct', status_code=201)
async def direct(body: DirectRequest, request: Request, response: Response):
    return await execute(request, response, movements.create_movement, body.student_id,
                         body.destination_department_id, None, True, write=True)


@router.post('/movements/{movement_id}/arrive')
async def arrive(movement_id: Annotated[int, Path(gt=0)], request: Request, response: Response):
    return await execute(request, response, movements.transition, movement_id, 'arrive', write=True)


@router.post('/movements/{movement_id}/finish')
async def finish(movement_id: Annotated[int, Path(gt=0)], request: Request, response: Response):
    return await execute(request, response, movements.transition, movement_id, 'finish', write=True)


@router.post('/movements/{movement_id}/cancel')
async def cancel(movement_id: Annotated[int, Path(gt=0)], request: Request, response: Response):
    return await execute(request, response, movements.transition, movement_id, 'cancel', write=True)


@router.get('/departments/{department_id}/active-movements')
async def active(department_id: Annotated[int, Path(gt=0)], request: Request, response: Response):
    return await execute(request, response, movements.list_active, department_id)


@router.get('/students/{student_id}/operational-status')
async def status(student_id: Annotated[int, Path(gt=0)], request: Request, response: Response):
    return await execute(request, response, movements.student_status, student_id)
