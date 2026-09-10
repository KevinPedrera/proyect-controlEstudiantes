from datetime import timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from starlette.datastructures import UploadFile

from app.import_api import cleanup_expired
from app.student_models import AcademicPeriod, ImportBatch, ImportRow, Institution, Student, StudentAcademicPlacement, StudentContact, utcnow
from import_fixtures import binary, upload, workbook


def seed(client, *, document='0123456789', first_name='Ana', course='Séptimo', contact=False):
    with client.app.state.session_factory() as session:
        period = session.scalar(select(AcademicPeriod))
        if period is None:
            period = AcademicPeriod(label='2026 - 2027', period_key='2026-2027')
            session.add(period)
            session.flush()
        student = Student(first_name=first_name, last_name='Pérez', document=document, document_type='Cédula' if document else None)
        session.add(student)
        session.flush()
        session.add(StudentAcademicPlacement(student_id=student.id, academic_period_id=period.id, course=course, parallel='A', source_baseline={'course': course, 'parallel': 'A'}))
        if contact: session.add(StudentContact(student_id=student.id, type='MADRE', first_name='Familiar', mobile_phone='0991111111'))
        session.commit()
        return student.id


def snapshot(client):
    with client.app.state.engine.connect() as conn:
        return {table: [tuple(r) for r in conn.execute(text(f'SELECT * FROM {table} ORDER BY id'))] for table in ['departments', 'institution', 'academic_periods', 'students', 'student_contacts', 'student_academic_placements']}


def preview_rows(client, response):
    assert response.status_code == 201, response.text
    return client.get(f"/api/student-imports/{response.json()['id']}/rows").json()['items']


def test_preview_is_non_destructive_and_recovers_snapshot(client):
    seed(client, contact=True)
    before = snapshot(client)
    response = upload(client)
    rows = preview_rows(client, response)
    assert snapshot(client) == before
    assert rows[0]['category'] == 'SIN_CAMBIOS'
    assert rows[0]['differences'] == []  # Missing contact blocks preserve existing data.
    assert response.json()['institution'] == 'Colegio de prueba'
    assert response.json()['emergency_blocks'] == 2
    assert response.headers['cache-control'] == 'no-store'
    recovered = client.get(f"/api/student-imports/{response.json()['id']}")
    assert recovered.json() == response.json()
    assert set(response.json()['counts']) == {'NUEVO','SIN_CAMBIOS','ACTUALIZACION','REQUIERE_REVISION'}
    assert sum(response.json()['counts'].values()) == 1


def test_first_preview_leaves_all_operational_tables_empty(client):
    before = snapshot(client)
    rows = preview_rows(client, upload(client))
    assert rows[0]['category'] == 'NUEVO'
    assert snapshot(client) == before


@pytest.mark.parametrize('fields,warning_code', [
    ({'N': 'Familiar', 'L': 'Ejemplo', 'O': '-'}, 'LITERAL_DASH'),
    ({'AE': 'Familiar'}, 'INCOMPLETE_CONTACT'),
    ({'H': '-'}, 'LITERAL_DASH'),
    ({'C': 'invalid'}, 'DOCUMENT_REVIEW'),
])
def test_new_student_quality_warning_is_not_a_blocker(client, fields, warning_code):
    before = snapshot(client)
    response = upload(client, binary(workbook([fields])))
    row = preview_rows(client, response)[0]
    assert row['category'] == 'NUEVO'
    assert warning_code in [w['code'] for w in row['warnings']]
    assert row['blocking_review_reasons'] == row['conflicts'] == []
    assert response.json()['rows_with_warnings'] == 1
    assert response.json()['rows_with_blocking_reasons'] == 0
    if 'O' in fields:
        assert row['contacts'][0]['middle_name'] == '-'
    assert snapshot(client) == before


@pytest.mark.parametrize('with_warning', [False, True])
def test_ambiguous_identity_stays_blocked_independently_of_quality(client, with_warning):
    seed(client)
    seed(client, document='9876543210')
    row = preview_rows(client, upload(client, binary(workbook([{'O': '-'} if with_warning else {}]))))[0]
    assert len(row['candidates']) == 2
    assert row['category'] == 'REQUIERE_REVISION'
    assert row['blocking_review_reasons'] == row['conflicts']
    assert row['blocking_review_reasons']
    assert bool(row['warnings']) == with_warning


def test_conflicting_document_is_a_blocking_reason(client):
    seed(client)
    row = preview_rows(client, upload(client, binary(workbook([{'C': '9876543210'}]))))[0]
    assert row['category'] == 'REQUIERE_REVISION'
    assert row['blocking_review_reasons']
    assert row['warnings'] == []


@pytest.mark.parametrize('field', ['G', 'E', 'I', 'J'])
def test_dash_in_minimum_field_remains_blocking(client, field):
    row = preview_rows(client, upload(client, binary(workbook([{field: '-'}]))))[0]
    assert row['category'] == 'REQUIERE_REVISION'
    assert row['errors'] and row['blocking_review_reasons']
    assert any(w['code'] == 'LITERAL_DASH' for w in row['warnings'])


@pytest.mark.parametrize('same_contact,expected', [(False, 'ACTUALIZACION'), (True, 'SIN_CAMBIOS')])
def test_matched_student_category_is_independent_of_contact_warning(client, same_contact, expected):
    identifier = seed(client)
    if same_contact:
        with client.app.state.session_factory() as session:
            session.add(StudentContact(student_id=identifier, type='REPRESENTANTE_LEGAL', first_name='Familiar', last_name='Ejemplo', middle_name='-'))
            session.commit()
    row = preview_rows(client, upload(client, binary(workbook([{'N': 'Familiar', 'L': 'Ejemplo', 'O': '-'}]))))[0]
    assert row['category'] == expected
    assert row['blocking_review_reasons'] == []
    assert row['warnings'] and row['contacts'][0]['middle_name'] == '-'


def test_quality_warning_does_not_suppress_reliable_absences(client):
    seed(client, document='9876543210', first_name='Otra')
    response = upload(client, binary(workbook([{'O': '-'}])), scope='PADRON_COMPLETO')
    assert response.json()['absences_calculated']
    assert response.json()['absence_count'] == 1
    assert response.json()['rows_with_blocking_reasons'] == 0


def test_optional_document_dash_does_not_create_false_duplicates(client):
    response = upload(client, binary(workbook([{'C': '-', 'G': 'Una'}, {'C': '-', 'G': 'Otra'}])))
    rows = preview_rows(client, response)
    assert all(r['category'] == 'NUEVO' for r in rows)
    assert all(r['student']['document'] == '-' and r['warnings'] for r in rows)
    assert all(r['blocking_review_reasons'] == [] for r in rows)


@pytest.mark.parametrize('overrides,expected,tag', [({}, 'SIN_CAMBIOS', None), ({'I': 'Octavo'}, 'ACTUALIZACION', 'CURSO'), ({'J':'B'}, 'ACTUALIZACION', 'PARALELO'), ({'H':'Andrés'}, 'REQUIERE_REVISION', 'DATOS_PERSONALES'), ({'C':'9999999999'}, 'REQUIERE_REVISION','DOCUMENTO')])
def test_categories_and_explicit_differences(client, overrides, expected, tag):
    seed(client)
    row = preview_rows(client, upload(client, binary(workbook([overrides]))))[0]
    assert row['category'] == expected
    if tag: assert tag in row['tags']


def test_manual_student_without_document_is_candidate_not_new(client):
    identifier = seed(client, document=None)
    row = preview_rows(client, upload(client))[0]
    assert row['category'] == 'REQUIERE_REVISION'
    assert row['candidates'][0]['student_id'] == identifier
    assert snapshot(client)['students'][0][5] is None  # Document remains absent.


@pytest.mark.parametrize('second', [{}, {'C': '9999999999'}, {'G': 'Otra'}])
def test_duplicate_rows_and_competing_candidates(client, second):
    seed(client)
    rows = preview_rows(client, upload(client, binary(workbook([{}, second]))))
    assert all(r['category'] == 'REQUIERE_REVISION' for r in rows)
    assert all(r['conflicts'] for r in rows)


def test_empty_incoming_value_preserves_existing_proposal(client):
    seed(client)
    before = snapshot(client)
    row = preview_rows(client, upload(client, binary(workbook([{'C':None}]))))[0]
    assert row['student']['document'] is None  # Received evidence remains available.
    assert row['category'] == 'REQUIERE_REVISION'  # No strong documentary match.
    assert row['blocking_review_reasons']
    assert snapshot(client) == before


@pytest.mark.parametrize('scope,expected', [('SUBCONJUNTO',0),('PADRON_COMPLETO',1)])
def test_absences_are_separate_and_never_change_placement(client, scope, expected):
    seed(client, document='9999999999', first_name='Otra')
    before = snapshot(client)
    response = upload(client, scope=scope)
    assert response.json()['absence_count']==expected
    page = client.get(f"/api/student-imports/{response.json()['id']}/absences").json()
    assert page['total']==expected
    assert snapshot(client)==before


def test_ambiguity_or_institution_conflict_suppresses_absences(client):
    seed(client, document=None)
    seed(client, document='9999999999', first_name='Otra')
    response = upload(client, scope='PADRON_COMPLETO')
    assert not response.json()['absences_calculated']
    with client.app.state.session_factory() as session:
        session.add(Institution(id=1, name='Otro colegio'))
        session.commit()
    response = upload(client, scope='PADRON_COMPLETO')
    assert response.json()['warnings'] and response.json()['absence_count']==0


def test_pagination_is_bounded_and_stable(client):
    response = upload(client, binary(workbook([{'C':str(i), 'G':f'Nombre{i}'} for i in range(5)])))
    prefix = f"/api/student-imports/{response.json()['id']}/rows"
    page = client.get(prefix+'?page=2&page_size=2').json()
    assert page['total']==5 and [r['row_number'] for r in page['items']]==[10,11]
    assert client.get(prefix+'?page_size=101').status_code==422
    assert client.get(prefix+'?page=0').status_code==422


def test_ttl_exact_boundary_cleans_all_personal_payload(client):
    response = upload(client)
    identifier = response.json()['id']
    factory = client.app.state.session_factory
    with factory() as session:
        batch = session.get(ImportBatch, identifier)
        assert batch.expires_at - batch.created_at == timedelta(hours=24)
        expiry = batch.expires_at
    assert cleanup_expired(factory, expiry - timedelta(microseconds=1))==0
    assert cleanup_expired(factory, expiry)==1
    assert cleanup_expired(factory, expiry)==0
    for suffix in ['', '/rows', '/absences']:
        assert client.get(f'/api/student-imports/{identifier}'+suffix).status_code==410
    with factory() as session:
        assert session.get(ImportBatch, identifier).proposal is None
        assert list(session.scalars(select(ImportRow)))==[]


@pytest.mark.parametrize('valid', [True,False])
def test_upload_temporary_is_closed_on_success_and_failure(client, valid):
    closed=[]
    original=UploadFile.close
    async def record(file):
        await original(file)
        closed.append(file.file.closed)
    with patch.object(UploadFile,'close',record):
        response=upload(client, None if valid else b'bad xlsx')
    assert response.status_code==(201 if valid else 422)
    assert closed and all(closed)


def test_no_future_endpoints_and_safe_errors(client, caplog):
    response=upload(client,b'PRIVATE DOCUMENT 9999999999')
    assert response.status_code==422
    assert '9999999999' not in response.text+caplog.text
    assert upload(client,scope='INVALID').status_code==422
    for path in ['resolutions']:
        assert client.post('/api/student-imports/00000000-0000-0000-0000-000000000000/'+path).status_code==404
    assert client.post('/api/students').status_code==404
    assert client.get('/api/students').status_code==404


def test_open_placement_uniqueness_and_foreign_keys(client):
    identifier=seed(client)
    with client.app.state.session_factory() as session:
        period=session.scalar(select(AcademicPeriod))
        session.add(StudentAcademicPlacement(student_id=identifier,academic_period_id=period.id,course='Octavo',parallel='B'))
        with pytest.raises(IntegrityError): session.commit()
    with client.app.state.engine.begin() as conn:
        with pytest.raises(IntegrityError): conn.execute(text("INSERT INTO institution(id,name,active_academic_period_id) VALUES(1,'Colegio',999)"))


def test_startup_removes_expired_drafts_without_a_get(client):
    from fastapi.testclient import TestClient
    from app.main import create_app
    identifier=upload(client).json()['id']
    with client.app.state.session_factory() as session:
        batch=session.get(ImportBatch,identifier)
        batch.created_at=utcnow()-timedelta(days=2)
        batch.expires_at=batch.created_at+timedelta(hours=24)
        session.commit()
    with TestClient(create_app(client.app.state.settings)) as restarted:
        with restarted.app.state.session_factory() as session:
            assert session.get(ImportBatch,identifier).proposal is None
            assert list(session.scalars(select(ImportRow)))==[]


def test_periodic_cleanup_runs_without_requests(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    from app import import_api
    sleep=AsyncMock(side_effect=[None, asyncio.CancelledError()])
    work=AsyncMock()
    monkeypatch.setattr(import_api.asyncio,'sleep',sleep)
    monkeypatch.setattr(import_api,'run_in_threadpool',work)
    with pytest.raises(asyncio.CancelledError): asyncio.run(import_api.cleanup_loop('factory'))
    work.assert_awaited_once_with(import_api.cleanup_expired,'factory')
    assert sleep.call_args.args==(60,)


def test_emergency_reordering_does_not_create_changes(client):
    identifier=seed(client)
    with client.app.state.session_factory() as session:
        session.add_all([StudentContact(student_id=identifier,type='EMERGENCIA',first_name=name,last_name='Familiar') for name in ['Uno','Dos']])
        session.commit()
    row=preview_rows(client,upload(client,binary(workbook([{'AE':'Dos','AF':'Familiar','AK':'Uno','AL':'Familiar'}]))))[0]
    assert row['category']=='SIN_CAMBIOS'


def test_oversized_http_body_rejected_before_parse(client):
    response=client.post('/api/student-imports/preview',content=b'x',headers={'Content-Length':str(6*1024*1024)})
    assert response.status_code==413


def test_operational_constraints_and_multiple_emergencies(client):
    identifier=seed(client)
    with client.app.state.session_factory() as session:
        session.add_all([StudentContact(student_id=identifier,type='EMERGENCIA') for _ in range(2)])
        session.commit()
    with client.app.state.session_factory() as session:
        session.add_all([StudentContact(student_id=identifier,type='MADRE') for _ in range(2)])
        with pytest.raises(IntegrityError): session.commit()
    with client.app.state.engine.begin() as conn:
        with pytest.raises(IntegrityError): conn.execute(text("UPDATE students SET first_name=''"))
        with pytest.raises(IntegrityError): conn.execute(text("UPDATE student_academic_placements SET parallel=''"))


def test_api_access_itself_purges_expired_personal_content(client):
    identifier = upload(client).json()['id']
    with client.app.state.session_factory() as session:
        batch = session.get(ImportBatch, identifier)
        batch.created_at = utcnow() - timedelta(days=2)
        batch.expires_at = batch.created_at + timedelta(hours=24)
        session.commit()
    assert client.get(f'/api/student-imports/{identifier}/rows').status_code == 410
    with client.app.state.session_factory() as session:
        batch = session.get(ImportBatch, identifier)
        assert batch.status == 'EXPIRED' and batch.proposal is None
        assert list(session.scalars(select(ImportRow))) == []


def test_chunked_oversized_upload_returns_413(client):
    def body():
        yield b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="test.xlsx"\r\nContent-Type: application/octet-stream\r\n\r\n'
        for _ in range(7):
            yield b'x' * 1024 * 1024
        yield b'\r\n--boundary--\r\n'
    response = client.post('/api/student-imports/preview', content=body(), headers={'Content-Type': 'multipart/form-data; boundary=boundary'})
    assert response.status_code == 413


def test_malformed_multipart_is_safe_client_error(client):
    response = client.post('/api/student-imports/preview', content=b'PRIVATE INPUT', headers={'Content-Type': 'multipart/form-data'})
    assert response.status_code == 400
    assert 'PRIVATE INPUT' not in response.text


@pytest.mark.parametrize('valid', [True, False])
def test_disk_upload_temporary_removed_on_success_and_error(client, valid):
    from io import BytesIO
    from zipfile import ZipFile, ZIP_STORED
    stream = BytesIO(binary(workbook()))
    with ZipFile(stream, 'a') as archive:
        archive.writestr('padding.bin', b'x' * (2 * 1024 * 1024), compress_type=ZIP_STORED)
    closed = []
    original = UploadFile.close
    async def record(file):
        rolled = file.file._rolled
        await original(file)
        closed.append((rolled, file.file.closed))
    with patch.object(UploadFile, 'close', record):
        response = upload(client, stream.getvalue(), scope='SUBCONJUNTO' if valid else 'INVALID')
    assert response.status_code == (201 if valid else 422)
    assert closed == [(True, True)]
