"""Synthetic students only; search never reads an institutional workbook."""

from datetime import timedelta
import logging

import pytest
from sqlalchemy import event, select, text

from app.search_logging import SearchQueryRedaction
from app.student_models import AcademicPeriod, Institution, Student, StudentAcademicPlacement, StudentContact, utcnow


def configure(client):
    with client.app.state.session_factory() as session:
        period = AcademicPeriod(label='Periodo de prueba', period_key='2030-2031')
        session.add(period)
        session.flush()
        session.add(Institution(id=1, name='Colegio sintético', active_academic_period_id=period.id))
        session.commit()
        return period.id


def add_student(client, period, *, first='José', middle='Juan', last='Pérez', second='López', active=True, closed=False, course='Octavo', parallel='A'):
    with client.app.state.session_factory() as session:
        student = Student(first_name=first, middle_name=middle, last_name=last, second_last_name=second,
                          active=active, document='9999999999', document_type='Cédula')
        session.add(student)
        session.flush()
        if period is not None:
            now = utcnow()
            session.add(StudentAcademicPlacement(student_id=student.id, academic_period_id=period,
                        course=course, parallel=parallel, recorded_from=now,
                        recorded_to=now + timedelta(seconds=1) if closed else None))
        session.add(StudentContact(student_id=student.id, type='MADRE', first_name='ContactoPrivado', mobile_phone='0987654321'))
        session.commit()
        return student.id


def search(client, q, **params):
    return client.get('/api/students/search', params={'q': q, **params})


@pytest.mark.parametrize('query', ['jose','JOSÉ','Jose\u0301','perez','lopez','juan','jose perez','perez jose','  JOSE   PEREZ  ','jua per','ose','jose juan perez lopez','lopez perez juan jose'])
def test_name_components_normalization_and_order(client, query):
    identifier = add_student(client, configure(client))
    response = search(client, query)
    assert response.status_code == 200
    assert [s['student_id'] for s in response.json()] == [identifier]
    assert response.json()[0]['display_name'] == 'José Juan Pérez López'
    assert response.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('query', ['', 'a', ' á ', ' - % _ ', '9999999999', '0987654321', 'ContactoPrivado', 'jose inexistente'])
def test_short_non_name_or_unmatched_queries_return_nothing(client, query):
    add_student(client, configure(client))
    assert search(client, query).json() == []


def test_period_and_active_student_filter_excludes_historical_placements(client):
    current = configure(client)
    with client.app.state.session_factory() as session:
        old = AcademicPeriod(label='Periodo anterior', period_key='2029-2030')
        session.add(old); session.commit(); old_id = old.id
    target = add_student(client, current)
    add_student(client, old_id)
    add_student(client, None)
    add_student(client, current, active=False)
    add_student(client, current, closed=True)
    with client.app.state.session_factory() as session:
        session.add(StudentAcademicPlacement(student_id=target, academic_period_id=old_id, course='Histórico', parallel='Z'))
        session.commit()
    found = search(client, 'jose').json()
    assert len(found) == 1 and found[0]['student_id'] == target
    assert found[0]['course'] == 'Octavo' and found[0]['parallel'] == 'A'
    with client.app.state.session_factory() as session:
        session.get(Institution, 1).active_academic_period_id = old_id
        session.commit()
    assert len(search(client, 'jose').json()) == 2  # Next query reads the new active period.


def test_relevance_and_stable_homonyms(client):
    period = configure(client)
    partial = add_student(client, period, first='Anabel', middle=None, last='Zeta', second=None)
    internal = add_student(client, period, first='Mariana', middle=None, last='Alba', second=None)
    direct1 = add_student(client, period, first='Ana', middle=None, last='Pérez', second=None)
    direct2 = add_student(client, period, first='Ana', middle=None, last='Pérez', second=None, parallel='B')
    alphabetical = add_student(client, period, first='Ana', middle=None, last='Alba', second=None)
    expected = [alphabetical, direct1, direct2, partial, internal]
    for _ in range(2):
        assert [s['student_id'] for s in search(client, 'ana').json()] == expected
    assert [s['student_id'] for s in search(client, 'perez ana').json()] == [direct1, direct2]


def test_full_name_equivalence_precedes_extra_name_components(client):
    period = configure(client)
    long_name = add_student(client, period, first='Ana', middle='María', last='Pérez', second=None)
    direct = add_student(client, period, first='Ana', middle=None, last='Pérez', second=None)
    assert [s['student_id'] for s in search(client, 'perez ana').json()] == [direct, long_name]


def test_default_and_explicit_result_limits(client):
    period = configure(client)
    for _ in range(8): add_student(client, period)
    assert len(search(client, 'jose').json()) == 5
    assert len(search(client, 'jose', limit=2).json()) == 2


@pytest.mark.parametrize('params', [{}, {'q':'ab','limit':'0'}, {'q':'ab','limit':'6'}, {'q':'ab','limit':'-1'}, {'q':'ab','limit':'1.5'}, {'q':'ab','limit':'private-value'}, {'q':'x'*121}, {'q':'ab','document':'private-value'}, [('q','ab'),('q','cd')], [('q','ab'),('limit','1'),('limit','2')]])
def test_invalid_parameters_are_safe(client, params, caplog):
    response = client.get('/api/students/search', params=params)
    assert response.status_code == 422
    assert 'private-value' not in response.text
    assert 'private-value' not in '\n'.join(r.getMessage() for r in caplog.records if r.name.startswith('app.'))
    assert response.headers['cache-control'] == 'no-store'


def test_missing_active_period_has_clear_error_and_short_query_does_not_scan(client):
    assert search(client, 'jose').status_code == 409
    assert search(client, 'j').json() == []


def test_minimal_dto_and_sql_do_not_load_family_or_document_data(client):
    identifier = add_student(client, configure(client))
    statements = []
    def executed(conn, cursor, statement, parameters, context, executemany): statements.append(statement)
    event.listen(client.app.state.engine, 'before_cursor_execute', executed)
    try:
        response = search(client, 'jose')
    finally:
        event.remove(client.app.state.engine, 'before_cursor_execute', executed)
    result = response.json()[0]
    assert set(result) == {'student_id','first_name','middle_name','last_name','second_last_name','display_name','course','parallel'}
    assert result['student_id'] == identifier
    assert not any(token in response.text for token in ['9999999999','0987654321','ContactoPrivado'])
    sql = '\n'.join(statements).lower()
    assert not any(token in sql for token in ['document', 'student_contacts', 'source_baseline', 'import_batches', 'import_rows'])


def test_search_does_not_change_original_names_or_operational_data(client):
    add_student(client, configure(client))
    def snapshot():
        with client.app.state.engine.connect() as conn:
            return {t:conn.execute(text('SELECT * FROM '+t)).all() for t in ('students','student_academic_placements','student_contacts','institution','academic_periods')}
    before = snapshot()
    assert search(client, ' JOSE   PEREZ ').status_code == 200
    assert snapshot() == before


def test_internal_error_does_not_log_or_return_query_or_database_details(client, monkeypatch, caplog):
    from app import student_search_api
    def fail(*args): raise RuntimeError('PRIVATE NAME 0987654321')
    monkeypatch.setattr(student_search_api, 'search_students', fail)
    response = search(client, 'PRIVATE NAME')
    assert response.status_code == 500
    own_logs = '\n'.join(r.getMessage() for r in caplog.records if r.name.startswith('app.'))
    assert 'PRIVATE' not in response.text + own_logs and '0987654321' not in response.text + own_logs


@pytest.mark.parametrize('path', ['/api/students/search?q=PRIVATE+NAME&limit=5','/api/students/search/?q=PRIVATE','/api/students/search?q=PRIVATE&limit=invalid'])
def test_access_log_hides_search_query(path):
    record = logging.LogRecord('uvicorn.access', logging.INFO, '', 0, '%s - "%s %s HTTP/%s" %d', ('client','GET',path,'1.1',200), None)
    assert SearchQueryRedaction().filter(record)
    assert 'PRIVATE' not in record.getMessage() and '?' not in record.getMessage()


def test_other_access_logs_stay_unchanged():
    args = ('client','GET','/api/health','1.1',200)
    record = logging.LogRecord('uvicorn.access', logging.INFO, '', 0, '%s %s %s %s %s', args, None)
    SearchQueryRedaction().filter(record)
    assert record.args == args
