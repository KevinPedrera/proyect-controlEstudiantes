"""Cuatro endpoints de preview. Ninguno aplica entidades operativas."""

import asyncio
from contextlib import suppress
from datetime import timedelta
import hashlib
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy import delete, func, inspect, select
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.import_comparison import compare_import
from app.import_parser import ImportFormatError, MAX_BYTES, PROFILE, parse_xlsx
from app.student_models import ImportBatch, ImportRow, utcnow

router = APIRouter(prefix='/student-imports')
logger = logging.getLogger(__name__)


class ImportBodyLimit:
    """Limita también uploads multipart antes de volcarlos completamente a disco."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('path') != '/api/student-imports/preview':
            return await self.app(scope, receive, send)
        limit = MAX_BYTES + 65536
        headers = dict(scope.get('headers', []))
        try:
            size = int(headers.get(b'content-length', b'0'))
        except ValueError:
            size = limit + 1
        if size > limit:
            return await JSONResponse({'detail': 'La carga supera el límite de 5 MB.'}, status_code=413)(scope, receive, send)
        consumed = 0
        async def bounded_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get('body', b''))
            if consumed > limit:
                # Starlette closes partial temporary files on MultiPartException.
                raise MultiPartException('La carga supera el límite permitido.')
            return message
        await self.app(scope, bounded_receive, send)


def cleanup_expired(factory, now=None) -> int:
    now = now or utcnow()
    with factory() as session:
        session.connection(execution_options={'sqlite_write': True})
        batches = list(session.scalars(select(ImportBatch).where(ImportBatch.expires_at <= now, ImportBatch.status == 'PREVIEW')))
        if not batches:
            return 0
        for batch in batches:
            session.execute(delete(ImportRow).where(ImportRow.batch_id == batch.id))
            batch.proposal = None
            batch.status = 'EXPIRED'
        session.commit()
        return len(batches)


async def cleanup_loop(factory):
    while True:
        await asyncio.sleep(60)
        try:
            await run_in_threadpool(cleanup_expired, factory)
        except Exception:
            logger.error('No se pudo limpiar los borradores; se reintentará. Sin detalle de datos.')


async def start_cleanup(app):
    if not await run_in_threadpool(lambda: inspect(app.state.engine).has_table('import_batches')):
        return None
    await run_in_threadpool(cleanup_expired, app.state.session_factory)
    return asyncio.create_task(cleanup_loop(app.state.session_factory))


async def stop_cleanup(task):
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def _summary(batch):
    proposal = batch.proposal or {}
    return {'id': batch.id, 'status': batch.status, 'profile': batch.profile, 'scope': batch.scope, 'created_at': batch.created_at.isoformat() + 'Z', 'expires_at': batch.expires_at.isoformat() + 'Z', **{k: v for k, v in proposal.items() if k not in ('absences', 'snapshot_revision')}, 'absence_count': len(proposal.get('absences', []))}


def create_preview(factory, content: bytes, scope: str):
    parsed = parse_xlsx(content)
    cleanup_expired(factory)
    # Snapshot comparison is read-only. The later write touches only draft tables.
    with factory() as session:
        proposal = compare_import(session, parsed, scope)
    rows = proposal.pop('rows')
    now = utcnow()
    with factory() as session:
        batch = ImportBatch(id=str(uuid4()), profile=PROFILE, file_hash=hashlib.sha256(content).hexdigest(), scope=scope, status='PREVIEW', created_at=now, expires_at=now + timedelta(hours=24), proposal=proposal)
        session.add(batch)
        session.flush()
        session.add_all(ImportRow(batch_id=batch.id, row_number=row['row_number'], category=row['category'], payload=row) for row in rows)
        session.commit()
        return _summary(batch)


def read_preview(factory, identifier: str, kind: str, page: int, page_size: int):
    cleanup_expired(factory)
    with factory() as session:
        batch = session.get(ImportBatch, identifier)
        if batch is None:
            raise HTTPException(404, 'No se encontró la previsualización.')
        if batch.status != 'PREVIEW' or batch.expires_at <= utcnow():
            raise HTTPException(410, 'La previsualización venció. Genera una nueva.')
        if kind == 'summary':
            return _summary(batch)
        offset = (page - 1) * page_size
        if kind == 'rows':
            total = session.scalar(select(func.count()).select_from(ImportRow).where(ImportRow.batch_id == identifier))
            items = [r.payload for r in session.scalars(select(ImportRow).where(ImportRow.batch_id == identifier).order_by(ImportRow.row_number).offset(offset).limit(page_size))]
        else:
            all_items = batch.proposal['absences']
            total, items = len(all_items), all_items[offset:offset + page_size]
        return {'items': items, 'total': total, 'page': page, 'page_size': page_size}


@router.post('/preview', status_code=201)
async def preview(request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    try:
        async with request.form(max_files=1, max_fields=1, max_part_size=1024) as form:
            if len(form.multi_items()) != 2 or set(form) != {'file', 'scope'}:
                raise HTTPException(422, 'Selecciona un archivo y declara el alcance del listado.')
            file, scope = form['file'], form['scope']
            if not isinstance(file, UploadFile) or scope not in ('PADRON_COMPLETO', 'SUBCONJUNTO'):
                raise HTTPException(422, 'Archivo o alcance inválido.')
            if not (file.filename or '').lower().endswith('.xlsx'):
                raise HTTPException(415, 'Selecciona un archivo .xlsx del perfil iDukay.')
            content = await file.read(MAX_BYTES + 1)
        # The uploaded temporary file is already closed on success and on error.
        return await run_in_threadpool(create_preview, request.app.state.session_factory, content, scope)
    except ImportFormatError as error:
        raise HTTPException(422, str(error)) from None
    except HTTPException:
        raise
    except StarletteHTTPException as error:
        if error.detail == 'La carga supera el límite permitido.':
            raise HTTPException(413, 'La carga supera el límite de 5 MB.') from None
        raise HTTPException(400, 'La carga multipart no es válida.') from None
    except Exception:
        logger.error('No se pudo generar la previsualización. Sin detalle de datos.')
        raise HTTPException(500, 'No se pudo generar la previsualización. Intenta nuevamente.') from None


async def _read(request, response, identifier, kind, page, page_size):
    response.headers['Cache-Control'] = 'no-store'
    try:
        return await run_in_threadpool(read_preview, request.app.state.session_factory, str(identifier), kind, page, page_size)
    except HTTPException:
        raise
    except Exception:
        logger.error('No se pudo recuperar la previsualización. Sin detalle de datos.')
        raise HTTPException(500, 'No se pudo recuperar la previsualización.') from None


@router.get('/{identifier}')
async def summary(identifier: UUID, request: Request, response: Response):
    return await _read(request, response, identifier, 'summary', 1, 25)


@router.get('/{identifier}/rows')
async def rows(identifier: UUID, request: Request, response: Response, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    return await _read(request, response, identifier, 'rows', page, page_size)


@router.get('/{identifier}/absences')
async def absences(identifier: UUID, request: Request, response: Response, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    return await _read(request, response, identifier, 'absences', page, page_size)
