"""Minimal search DTO and input errors that never echo the name query."""

import logging
import sqlite3

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy.exc import OperationalError

from app.student_search import ActivePeriodMissing, MAX_QUERY_LENGTH, MAX_RESULTS, StudentSearchResult, search_students

router = APIRouter(prefix='/students')
logger = logging.getLogger(__name__)


def _error(status: int, message: str):
    return HTTPException(status, message, headers={'Cache-Control': 'no-store'})


@router.get('/search', response_model=list[StudentSearchResult])
def search(request: Request, response: Response):
    # Manual validation avoids FastAPI's default inclusion of rejected input in
    # error bodies. Neither invalid q nor invalid limit is reflected to clients.
    params = request.query_params
    if set(params) - {'q', 'limit'} or len(params.getlist('q')) != 1 or len(params.getlist('limit')) > 1:
        raise _error(422, 'Indica una consulta de nombres y un límite válido.')
    query = params['q']
    raw_limit = params.get('limit', str(MAX_RESULTS))
    if len(query) > MAX_QUERY_LENGTH or not raw_limit.isascii() or not raw_limit.isdecimal() or len(raw_limit) > 2:
        raise _error(422, 'La consulta admite hasta 120 caracteres y el límite debe estar entre 1 y 5.')
    limit = int(raw_limit)
    if not 1 <= limit <= MAX_RESULTS:
        raise _error(422, 'El límite debe estar entre 1 y 5.')
    response.headers['Cache-Control'] = 'no-store'
    try:
        return search_students(request.app.state.session_factory, query, limit)
    except ActivePeriodMissing:
        raise _error(409, 'No hay un periodo académico activo configurado para buscar estudiantes.') from None
    except OperationalError as error:
        code = getattr(error.orig, 'sqlite_errorcode', 0)
        if code & 0xFF in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
            raise _error(503, 'La búsqueda no está disponible momentáneamente. Intenta nuevamente.') from None
        logger.error('No se pudo consultar estudiantes. Sin detalle de datos.')
        raise _error(500, 'No pudimos realizar la búsqueda. Intenta nuevamente.') from None
    except Exception:
        logger.error('No se pudo consultar estudiantes. Sin detalle de datos.')
        raise _error(500, 'No pudimos realizar la búsqueda. Intenta nuevamente.') from None
