"""Preview temporal y confirmación explícita, atómica e idempotente."""

import asyncio
from contextlib import suppress
from datetime import timedelta
import hashlib
import json
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import OperationalError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from app.import_comparison import APPLICATION_CONTRACT_VERSION, compare_import, snapshot_revision
from app.import_parser import ImportFormatError, MAX_BYTES, PROFILE, parse_xlsx
from app.student_models import AcademicPeriod, ImportBatch, ImportRow, Institution, Student, StudentAcademicPlacement, StudentContact, utcnow

router = APIRouter(prefix='/student-imports')
logger = logging.getLogger(__name__)


class ConfirmImport(BaseModel):
    """The client authorizes a saved preview; it never supplies operational data."""
    model_config = ConfigDict(extra='forbid', strict=True)
    confirm: bool
    accept_configuration: bool = False


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
        batches = list(session.scalars(select(ImportBatch).where(
            ImportBatch.expires_at <= now,
            (ImportBatch.status == 'PREVIEW') | ((ImportBatch.status == 'APPLIED') & ImportBatch.proposal.is_not(None)),
        )))
        if not batches:
            return 0
        for batch in batches:
            session.execute(delete(ImportRow).where(ImportRow.batch_id == batch.id))
            batch.proposal = None
            if batch.status == 'PREVIEW':
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
    result = {'id': batch.id, 'status': batch.status, 'profile': batch.profile, 'scope': batch.scope, 'created_at': batch.created_at.isoformat() + 'Z', 'expires_at': batch.expires_at.isoformat() + 'Z'}
    if batch.status == 'APPLIED':
        result['applied_receipt'] = batch.applied_result
        result['confirmable'] = False
        return result
    result.update({k: v for k, v in proposal.items() if k not in ('absences', 'snapshot_revision', 'rows', 'rows_digest')})
    result['absence_count'] = len(proposal.get('absences', []))
    result['confirmable'] = bool(batch.status == 'PREVIEW' and batch.application_contract_version == APPLICATION_CONTRACT_VERSION and not proposal.get('rows_with_blocking_reasons', 0) and proposal.get('configuration', {}).get('action') != 'INCOMPATIBLE')
    result['applied_receipt'] = None
    return result


def _rows_digest(rows) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str).encode()).hexdigest()


def create_preview(factory, content: bytes, scope: str):
    parsed = parse_xlsx(content)
    cleanup_expired(factory)
    # Snapshot comparison is read-only. The later write touches only draft tables.
    with factory() as session:
        proposal = compare_import(session, parsed, scope)
    rows = proposal.pop('rows')
    proposal['rows_digest'] = _rows_digest(rows)
    now = utcnow()
    with factory() as session:
        batch = ImportBatch(id=str(uuid4()), profile=PROFILE, file_hash=hashlib.sha256(content).hexdigest(), scope=scope, status='PREVIEW', created_at=now, expires_at=now + timedelta(hours=24), proposal=proposal, application_contract_version=APPLICATION_CONTRACT_VERSION)
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
        if batch.status == 'APPLIED':
            if kind == 'summary':
                return _summary(batch)
            if batch.proposal is None or batch.expires_at <= utcnow():
                raise HTTPException(410, 'El contenido temporal de esta importación aplicada venció.')
        if batch.status != 'PREVIEW' and batch.status != 'APPLIED' or batch.expires_at <= utcnow() and batch.status != 'APPLIED':
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


def _domain(code: str, message: str, status: int = 409) -> HTTPException:
    return HTTPException(status, {'code': code, 'message': message})


def _receipt(batch: ImportBatch) -> dict:
    return _summary(batch)


def _update_accepted_fields(entity, values, batch_id, now):
    """Advance BASE only for fields actually written; never absorb manual values."""
    baseline = dict(entity.source_baseline or {})
    protected = set(entity.manual_protected_fields or [])
    changed = False
    for field, value in values.items():
        if field == 'type' or getattr(entity, field) == value:
            continue
        old = getattr(entity, field)
        if field in protected or field not in baseline or baseline[field] != old:
            raise _domain('PROCEDENCIA_INCOMPATIBLE', 'La procedencia de un campo no permite actualizarlo.')
        if value is None or (value == '-' and old not in (None, '', '-')):
            raise _domain('PREVIEW_INTEGRO_INVALIDO', 'El plan no conserva los valores existentes.')
        setattr(entity, field, value)
        baseline[field] = value
        changed = True
    if changed:
        entity.source_baseline = baseline
        entity.source_batch_id = batch_id
        entity.updated_at = now


def _apply_row(session, batch: ImportBatch, row: ImportRow, period: AcademicPeriod, now) -> None:
    plan = row.payload.get('application_plan')
    if not plan:
        raise _domain('PREVIEW_INTEGRO_INVALIDO', 'El borrador no contiene un plan de aplicación válido.')
    if row.category == 'SIN_CAMBIOS':
        return
    if plan['action'] == 'CREATE':
        values = plan['values']
        student = Student(**values, source_batch_id=batch.id, source_baseline=dict(values), manual_protected_fields=[], created_at=now, updated_at=now)
        session.add(student)
        session.flush()
    else:
        student = session.get(Student, plan['student_id'])
        if student is None or not student.active:
            raise _domain('PREVIEW_OBSOLETO', 'El estado operativo cambió. Genera una nueva previsualización.')
        _update_accepted_fields(student, plan['values'], batch.id, now)

    placement = plan['placement']
    if placement['action'] != 'NOOP':
        current = session.scalar(select(StudentAcademicPlacement).where(
            StudentAcademicPlacement.student_id == student.id,
            StudentAcademicPlacement.academic_period_id == period.id,
            StudentAcademicPlacement.recorded_to.is_(None),
        ))
        values = {field: placement[field] for field in ('course', 'parallel')}
        baseline, protected = dict(values), []
        if placement['action'] == 'REPLACE':
            if current is None:
                raise _domain('PREVIEW_OBSOLETO', 'La ubicación académica cambió. Genera una nueva previsualización.')
            baseline = dict(current.source_baseline or {})
            protected = list(current.manual_protected_fields or [])
            for field, value in values.items():
                if getattr(current, field) != value:
                    if field in protected or field not in baseline or baseline[field] != getattr(current, field):
                        raise _domain('PROCEDENCIA_INCOMPATIBLE', 'La ubicación académica no permite la actualización propuesta.')
                    baseline[field] = value
            current.recorded_to = now
            # Release the partial unique index before inserting the new version.
            session.flush()
        elif current is not None:
            raise _domain('PREVIEW_OBSOLETO', 'Ya existe una ubicación en el periodo de destino.')
        session.add(StudentAcademicPlacement(
            student_id=student.id, academic_period_id=period.id, **values,
            source_batch_id=batch.id, source_baseline=baseline,
            manual_protected_fields=protected, recorded_from=now,
        ))

    for contact_plan in plan['contacts']:
        values = contact_plan['values']
        if contact_plan['action'] == 'CREATE':
            session.add(StudentContact(student_id=student.id, **values, source_batch_id=batch.id, source_baseline=dict(values), manual_protected_fields=[], updated_at=now))
        elif contact_plan['action'] == 'UPDATE':
            contact = session.get(StudentContact, contact_plan['contact_id'])
            if contact is None or contact.student_id != student.id or not contact.active or contact.type != values['type']:
                raise _domain('PREVIEW_OBSOLETO', 'Los contactos cambiaron. Genera una nueva previsualización.')
            _update_accepted_fields(contact, values, batch.id, now)


def confirm_preview(factory, identifier: str, request: ConfirmImport) -> dict:
    if request.confirm is not True:
        raise _domain('CONFIRMACION_REQUERIDA', 'Confirma explícitamente la aplicación para continuar.', 422)
    try:
        with factory() as session:
            session.connection(execution_options={'sqlite_write': True})
            # This is intentionally after BEGIN IMMEDIATE: expiry during a valid
            # serialized transaction does not revoke the confirmation.
            now = utcnow()
            batch = session.get(ImportBatch, identifier)
            if batch is None:
                raise _domain('IMPORTACION_NO_ENCONTRADA', 'No se encontró la previsualización.', 404)
            if batch.status == 'APPLIED':
                return _receipt(batch)
            if batch.status != 'PREVIEW' or batch.expires_at <= now:
                raise _domain('PREVIEW_VENCIDO', 'La previsualización venció. Genera una nueva.', 410)
            if batch.application_contract_version != APPLICATION_CONTRACT_VERSION:
                raise _domain('CONTRATO_INCOMPATIBLE', 'Este borrador fue creado con reglas anteriores. Genera una nueva previsualización.')
            proposal = batch.proposal or {}
            rows = list(session.scalars(select(ImportRow).where(ImportRow.batch_id == batch.id).order_by(ImportRow.row_number)))
            counts = {key: sum(row.category == key for row in rows) for key in ('NUEVO', 'ACTUALIZACION', 'SIN_CAMBIOS', 'REQUIERE_REVISION')}
            if (not rows or len(rows) != proposal.get('total')
                    or _rows_digest([row.payload for row in rows]) != proposal.get('rows_digest')
                    or counts != proposal.get('counts')
                    or any(row.category != row.payload.get('category') or row.row_number != row.payload.get('row_number') for row in rows)):
                raise _domain('PREVIEW_INTEGRO_INVALIDO', 'El borrador no es íntegro. Genera una nueva previsualización.')
            if any(row.category == 'REQUIERE_REVISION' or row.payload.get('blocking_review_reasons') or row.payload.get('errors') or row.payload.get('conflicts') for row in rows):
                raise _domain('BLOQUEOS_PRESENTES', 'Hay registros que requieren revisión antes de aplicar el lote.')
            if snapshot_revision(session, proposal.get('period_key', '')) != proposal.get('snapshot_revision'):
                raise _domain('PREVIEW_OBSOLETO', 'El estado operativo cambió. Genera una nueva previsualización.')
            configuration = proposal.get('configuration') or {}
            if configuration.get('action') == 'INCOMPATIBLE':
                raise _domain('INSTITUCION_INCOMPATIBLE', 'La institución del borrador no coincide con la registrada.')
            if configuration.get('requires_acceptance') and not request.accept_configuration:
                raise _domain('CONFIGURACION_REQUIERE_CONFIRMACION', 'Confirma la configuración institucional y del periodo para continuar.')
            institution = session.get(Institution, 1)
            if institution is not None:
                from app.import_parser import comparison_key
                if comparison_key(institution.name) != comparison_key(proposal['institution']):
                    raise _domain('INSTITUCION_INCOMPATIBLE', 'La institución no coincide con la registrada.')
            if institution is None:
                institution = Institution(id=1, name=proposal['institution'])
                session.add(institution)
                session.flush()
            period = session.scalar(select(AcademicPeriod).where(AcademicPeriod.period_key == proposal['period_key']))
            if period is None:
                period = AcademicPeriod(label=proposal['academic_period'], period_key=proposal['period_key'])
                session.add(period); session.flush()
            if institution.active_academic_period_id != period.id:
                if not request.accept_configuration:
                    raise _domain('CONFIGURACION_REQUIERE_CONFIRMACION', 'Confirma el periodo académico activo para continuar.')
                institution.active_academic_period_id = period.id
            for row in rows: _apply_row(session, batch, row, period, now)
            batch.status, batch.applied_at = 'APPLIED', now
            batch.applied_result = {'import_id':batch.id, 'status':'APPLIED', 'applied_at':now.isoformat() + 'Z', 'counts':counts}
            session.commit()
            return _receipt(batch)
    except OperationalError as error:
        if 'locked' in str(error).lower() or 'busy' in str(error).lower():
            raise _domain('BASE_OCUPADA', 'La base de datos está ocupada. Intenta nuevamente.', 503) from None
        raise


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


@router.post('/{identifier}/confirm')
async def confirm(identifier: UUID, request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    try:
        # Do not echo rejected input through FastAPI's default validation errors.
        try:
            body = ConfirmImport.model_validate(await request.json())
        except (ValidationError, ValueError):
            raise _domain('CONFIRMACION_INVALIDA', 'Envía únicamente la confirmación y aceptación de configuración.', 422) from None
        return await run_in_threadpool(confirm_preview, request.app.state.session_factory, str(identifier), body)
    except HTTPException:
        raise
    except Exception:
        logger.error('No se pudo confirmar la importación. Sin detalle de datos.')
        raise _domain('ERROR_APLICACION', 'No se pudo confirmar la importación. Intenta recuperar su estado por identificador.', 500) from None


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
