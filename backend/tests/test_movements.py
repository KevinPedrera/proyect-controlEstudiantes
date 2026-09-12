"""Phase 5: synthetic operational records in isolated migrated databases."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError

from app.models import Department
from app.movement_models import Movement
from app.student_models import AcademicPeriod, Institution, Student, StudentAcademicPlacement, utcnow


@pytest.fixture
def students(client):
    with client.app.state.session_factory() as session:
        period = AcademicPeriod(label='Periodo sintético', period_key='test-5')
        session.add(period); session.flush()
        session.add(Institution(id=1, name='Colegio sintético', active_academic_period_id=period.id))
        identifiers = []
        for number in range(6):
            student = Student(first_name='Alumno', last_name=f'Sintético {number}')
            session.add(student); session.flush()
            session.add(StudentAcademicPlacement(student_id=student.id, academic_period_id=period.id,
                                                  course='Octavo sintético', parallel='A'))
            identifiers.append(student.id)
        session.commit()
    return identifiers


def create(client, student, destination=1, direct=False, **kwargs):
    return client.post('/api/movements' + ('/direct' if direct else ''), json={
        'student_id': student, 'destination_department_id': destination, **kwargs})


def act(client, movement, action):
    return client.post(f'/api/movements/{movement}/{action}', json={})


def panel(client, destination=1):
    response = client.get(f'/api/departments/{destination}/active-movements')
    assert response.status_code == 200
    return response.json()['items']


@pytest.mark.parametrize('direct', [False, True])
def test_creation_timestamps_placement_and_origin(client, students, direct):
    before = utcnow().isoformat()
    response = create(client, students[0], direct=direct, **({} if direct else {'origin_department_id': 2}))
    assert response.status_code == 201
    row = response.json()
    assert row['status'] == ('EN_ATENCION' if direct else 'EN_CAMINO')
    assert row['origin_department_id'] == (None if direct else 2)
    assert row['created_at'] >= before
    assert row['created_at'].endswith('+00:00')
    assert row['arrived_at' if direct else 'sent_at'] == row['created_at']
    assert row['sent_at' if direct else 'arrived_at'] is None
    assert row['finished_at'] is row['cancelled_at'] is None
    with client.app.state.session_factory() as session:
        placement = session.get(StudentAcademicPlacement, row['academic_placement_id'])
        assert placement.student_id == students[0]
    assert response.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('direct', [False, True])
@pytest.mark.parametrize('second_direct', [False, True])
def test_global_active_conflict(client, students, direct, second_direct):
    create(client, students[0], direct=direct)
    result = create(client, students[0], destination=2, direct=second_direct)
    assert result.status_code == 409
    assert result.json()['detail']['code'] == 'ESTUDIANTE_ACTIVO'
    assert len(panel(client)) == 1 and not panel(client, 2)


@pytest.mark.parametrize('flow', [('arrive','finish'), ('cancel',), ('direct','finish')])
def test_full_flow_and_idempotency_and_release(client, students, flow):
    direct = flow[0] == 'direct'
    row = create(client, students[0], direct=direct).json()
    manager = client.app.state.connection_manager
    manager.movements_changed = AsyncMock()
    for action in flow[1:] if direct else flow:
        first = act(client, row['id'], action)
        assert first.status_code == 200
        assert act(client, row['id'], action).json() == first.json()
    assert manager.movements_changed.await_count == (len(flow) - int(direct))
    assert not panel(client)
    assert create(client, students[0]).status_code == 201
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Movement)) == 2


@pytest.mark.parametrize('state,action', [('EN_CAMINO','finish'), ('EN_ATENCION','cancel'),
    ('FINALIZADO','arrive'), ('FINALIZADO','cancel'), ('CANCELADO','arrive'), ('CANCELADO','finish')])
def test_invalid_transitions(client, students, state, action):
    row = create(client, students[0]).json()
    if state in ('EN_ATENCION','FINALIZADO'): act(client, row['id'], 'arrive')
    if state == 'FINALIZADO': act(client, row['id'], 'finish')
    if state == 'CANCELADO': act(client, row['id'], 'cancel')
    assert act(client, row['id'], action).status_code == 409


@pytest.mark.parametrize('direct', [False, True])
def test_unavailable_and_inactive_destination(client, students, direct):
    client.put('/api/departments/1/availability', json={'availability':'NO_DISPONIBLE'})
    assert create(client, students[0], direct=direct).json()['detail']['code'] == 'DEPARTAMENTO_NO_DISPONIBLE'
    with client.app.state.session_factory() as session:
        session.get(Department, 1).active = False; session.commit()
    assert create(client, students[0], direct=direct).json()['detail']['code'] == 'DEPARTAMENTO_INACTIVO'


def test_authoritative_counts_change_and_existing_movements_survive(client, students):
    sent = create(client, students[0]).json()
    second = create(client, students[1]).json()
    direct = create(client, students[2], direct=True).json()
    url = '/api/departments/1/availability'
    first = client.put(url, json={'availability':'NO_DISPONIBLE'})
    counts = first.json()['detail']['active_counts']
    assert counts == {'en_camino':2, 'en_atencion':1}
    act(client, sent['id'], 'arrive')
    stale = client.put(url, json={'availability':'NO_DISPONIBLE', 'confirmed_active_counts':counts})
    assert stale.status_code == 409
    assert stale.json()['detail']['active_counts'] == {'en_camino':1, 'en_atencion':2}
    accepted = client.put(url, json={'availability':'NO_DISPONIBLE',
        'confirmed_active_counts':stale.json()['detail']['active_counts']})
    assert accepted.status_code == 200 and len(panel(client)) == 3
    assert act(client, sent['id'], 'finish').status_code == 200
    assert act(client, second['id'], 'cancel').status_code == 200
    assert act(client, direct['id'], 'finish').status_code == 200
    assert create(client, students[3]).status_code == 409


def test_arrival_after_department_closes(client, students):
    sent = create(client, students[0]).json()
    client.put('/api/departments/1/availability', json={'availability':'NO_DISPONIBLE',
        'confirmed_active_counts': {'en_camino':1,'en_atencion':0}})
    assert act(client, sent['id'], 'arrive').status_code == 200
    assert act(client, sent['id'], 'finish').status_code == 200


@pytest.mark.parametrize('directs', [(False,False), (True,True), (False,True)])
def test_concurrent_requests_create_exactly_one(client, students, directs):
    barrier = Barrier(2)
    def attempt(direct):
        barrier.wait()
        return create(client, students[0], direct=direct).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, directs)) == [201,409]
    assert len(panel(client)) == 1


def test_concurrent_close_and_send_are_serialized(client, students):
    barrier = Barrier(2)
    def send():
        barrier.wait(); return create(client, students[0])
    def close():
        barrier.wait(); return client.put('/api/departments/1/availability', json={'availability':'NO_DISPONIBLE'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        sending, closing = pool.submit(send), pool.submit(close)
        statuses = sending.result().status_code, closing.result().status_code
    assert statuses in ((201,409), (409,200))


def test_panels_order_scope_search_and_privacy(client, students):
    sent = create(client, students[0]).json()
    direct1 = create(client, students[1], direct=True).json()
    direct2 = create(client, students[2], direct=True).json()
    other = create(client, students[3], destination=2).json()
    assert [r['id'] for r in panel(client)] == [direct1['id'], direct2['id'], sent['id']]
    assert [r['id'] for r in panel(client,2)] == [other['id']]
    results = client.get('/api/students/search?q=Alumno').json()
    assert len(results) == 5
    assert results[0]['active_movement']['status'] == 'EN_CAMINO'
    assert set(results[0]['active_movement']) == {'status','destination_name'}
    for forbidden in ('document','phone','contact','source_baseline'):
        assert forbidden not in str(results) and forbidden not in str(panel(client))


def test_historical_placement_and_persistence(client, students):
    row = create(client, students[0]).json()
    with client.app.state.session_factory() as session:
        old = session.get(StudentAcademicPlacement, row['academic_placement_id'])
        old.recorded_to = utcnow(); session.flush()
        session.add(StudentAcademicPlacement(student_id=students[0], academic_period_id=old.academic_period_id,
            course='Noveno sintético', parallel='B')); session.commit()
    client.app.state.engine.dispose()
    assert panel(client)[0]['course'] == 'Octavo sintético'
    assert client.get('/api/students/search?q=Alumno').json()[0]['course'] == 'Noveno sintético'


def test_websocket_two_clients_after_commit_and_no_event_on_error(client, students):
    with client.websocket_connect('/ws') as one, client.websocket_connect('/ws') as two:
        row = create(client, students[0]).json()
        assert one.receive_json() == two.receive_json() == {'type':'movements_changed'}
        assert panel(client)[0]['id'] == row['id']
        create(client, students[0])  # Must emit nothing; next event is the arrival.
        act(client, row['id'], 'arrive')
        assert one.receive_json() == two.receive_json() == {'type':'movements_changed'}
        assert panel(client)[0]['status'] == 'EN_ATENCION'


def test_rollback_and_no_notification(client, students, monkeypatch):
    from app import movements
    manager = client.app.state.connection_manager
    manager.movements_changed = AsyncMock()
    def fail(*args): raise RuntimeError('synthetic failure')
    monkeypatch.setattr(movements, 'movement_result', fail)
    assert create(client, students[0]).status_code == 500
    manager.movements_changed.assert_not_awaited()
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Movement)) == 0


@pytest.mark.parametrize('status', ['EN_CAMINO','EN_ATENCION'])
def test_database_unique_constraint_independent_of_service(client, students, status):
    row = create(client, students[0]).json()
    with client.app.state.session_factory() as session:
        now = utcnow()
        session.add(Movement(student_id=students[0], academic_placement_id=row['academic_placement_id'],
            destination_department_id=2, status=status, sent_at=now if status == 'EN_CAMINO' else None,
            arrived_at=now if status == 'EN_ATENCION' else None, created_at=now, updated_at=now))
        with pytest.raises(IntegrityError): session.commit()


@pytest.mark.parametrize('assignment', ["status='OTRO'", "sent_at=NULL", "destination_department_id=99999", "academic_placement_id=99999", "arrived_at=created_at", "updated_at='2000-01-01'"])
def test_database_constraints(client, students, assignment):
    row = create(client, students[0]).json()
    with client.app.state.engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(text(f'UPDATE movements SET {assignment} WHERE id=:id'), {'id':row['id']})


@pytest.mark.parametrize('body', [{}, {'student_id':1}, {'student_id':True,'destination_department_id':1},
    {'student_id':1,'destination_department_id':0}, {'student_id':1,'destination_department_id':1,'sent_at':'2030'}])
def test_invalid_request(client, body):
    assert client.post('/api/movements', json=body).status_code == 422


def test_missing_and_inactive_domain_errors(client, students):
    assert create(client, 99999).status_code == 404
    assert create(client, students[0], destination=99999).status_code == 404
    assert act(client, 99999, 'arrive').status_code == 404
    assert create(client, students[0], origin_department_id=99999).status_code == 409
    with client.app.state.session_factory() as session:
        session.get(Student, students[0]).active=False
        session.get(Institution,1).active_academic_period_id=None
        session.commit()
    assert create(client, students[0]).json()['detail']['code'] == 'ESTUDIANTE_INACTIVO'
    assert create(client, students[1]).json()['detail']['code'] == 'UBICACION_NO_DISPONIBLE'
