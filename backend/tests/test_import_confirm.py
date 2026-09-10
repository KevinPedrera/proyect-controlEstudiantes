"""Synthetic confirmation tests.  No institutional workbook data is used here."""
from datetime import timedelta

import pytest
from sqlalchemy import func, select, text

from app.import_api import cleanup_expired
from app.student_models import AcademicPeriod, ImportBatch, ImportRow, Institution, Student, StudentAcademicPlacement, StudentContact, utcnow
from import_fixtures import binary, upload, workbook


def preview(client, rows=None, scope="SUBCONJUNTO"):
    response = upload(client, binary(workbook(rows)), scope)
    assert response.status_code == 201, response.text
    return response.json()


def confirm(client, identifier, accept=True):
    return client.post(f"/api/student-imports/{identifier}/confirm", json={"confirm": True, "accept_configuration": accept})


def count(session, model): return session.scalar(select(func.count()).select_from(model))


def test_first_apply_is_atomic_idempotent_and_receipt_recovers(client):
    draft = preview(client, [{}, {"C":"9876543210", "G":"Beto", "N":"Familiar", "L":"Uno"}])
    assert draft["confirmable"] and draft["contract_version"] == "3B-1"
    applied = confirm(client, draft["id"])
    assert applied.status_code == 200
    receipt = applied.json()
    assert receipt["applied_receipt"]["counts"]["NUEVO"] == 2 and "institution" not in receipt
    again = confirm(client, draft["id"])
    assert again.status_code == 200 and again.json() == receipt
    recovered = client.get(f"/api/student-imports/{draft['id']}")
    assert recovered.json()["status"] == "APPLIED" and recovered.json() == receipt
    with client.app.state.session_factory() as session:
        assert count(session, Student) == 2 and count(session, StudentAcademicPlacement) == 2
        assert count(session, StudentContact) == 1
        assert session.get(Institution, 1).active_academic_period_id is not None


def test_identical_reimport_is_noop_and_strong_match_beats_weak_candidates(client):
    # Same first/last names, but distinct full names and valid documents.
    rows = [{"H": "Primera"}, {"C": "9876543210", "H": "Segunda"}]
    first = preview(client, rows)
    assert confirm(client, first["id"]).status_code == 200
    second = preview(client, rows)
    assert second["counts"] == {"NUEVO":0, "SIN_CAMBIOS":2, "ACTUALIZACION":0, "REQUIERE_REVISION":0}
    with client.app.state.session_factory() as session:
        before = [(s.id, s.updated_at) for s in session.scalars(select(Student).order_by(Student.id))]
    assert confirm(client, second["id"], accept=False).status_code == 200
    with client.app.state.session_factory() as session:
        assert [(s.id, s.updated_at) for s in session.scalars(select(Student).order_by(Student.id))] == before


def test_warnings_allow_apply_but_blockers_and_old_contract_do_not(client):
    draft = preview(client, [{"O":"-"}, {"C":"0123456789"}])
    assert draft["counts"]["REQUIERE_REVISION"] == 2
    assert confirm(client, draft["id"]).status_code == 409
    valid = preview(client, [{"O":"-"}])
    assert confirm(client, valid["id"]).status_code == 200
    with client.app.state.session_factory() as session:
        old = ImportBatch(id="00000000-0000-0000-0000-000000000002", profile="old", file_hash="0" * 64, scope="SUBCONJUNTO", created_at=utcnow(), expires_at=utcnow()+timedelta(hours=1), status="PREVIEW", proposal={"total":0})
        session.add(old); session.commit()
    response = confirm(client, "00000000-0000-0000-0000-000000000002")
    assert response.status_code == 409 and response.json()["detail"]["code"] == "CONTRATO_INCOMPATIBLE"


def test_expiry_purges_personal_preview_but_keeps_applied_receipt(client):
    draft = preview(client)
    assert confirm(client, draft["id"]).status_code == 200
    with client.app.state.session_factory() as session:
        batch = session.get(ImportBatch, draft["id"])
        batch.created_at = utcnow() - timedelta(days=2); batch.expires_at = batch.created_at + timedelta(hours=24); session.commit()
    assert cleanup_expired(client.app.state.session_factory) == 1
    assert cleanup_expired(client.app.state.session_factory) == 0
    assert client.get(f"/api/student-imports/{draft['id']}").json()["status"] == "APPLIED"
    assert client.get(f"/api/student-imports/{draft['id']}/rows").status_code == 410
    with client.app.state.session_factory() as session:
        assert count(session, ImportRow) == 0 and session.get(ImportBatch, draft["id"]).proposal is None


def test_empty_and_dash_never_overwrite_accepted_or_protected_contact(client):
    first = preview(client, [{"N":"Familiar", "L":"Uno", "O":"Valor", "Q":"0991111111"}])
    assert confirm(client, first["id"]).status_code == 200
    with client.app.state.session_factory() as session:
        contact = session.scalar(select(StudentContact)); contact.manual_protected_fields = ["mobile_phone"]; session.commit()
    second = preview(client, [{"N":"Familiar", "L":"Uno", "O":"-", "Q":"0992222222"}])
    assert second["counts"]["ACTUALIZACION"] == 0
    assert confirm(client, second["id"], accept=False).status_code == 200
    with client.app.state.session_factory() as session:
        contact = session.scalar(select(StudentContact))
        assert contact.middle_name == "Valor" and contact.mobile_phone == "0991111111"


def test_obsolete_preview_and_period_change_require_explicit_acceptance(client):
    one, two = preview(client), preview(client)
    assert confirm(client, one["id"]).status_code == 200
    stale = confirm(client, two["id"])
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "PREVIEW_OBSOLETO"
    with client.app.state.session_factory() as session:
        period = session.scalar(select(AcademicPeriod)); period.period_key, period.label = "2025-2026", "Año Lectivo 2025 - 2026"; session.commit()
    different = preview(client)
    assert different["configuration"]["requires_acceptance"]
    assert confirm(client, different["id"], accept=False).status_code == 409


def operational_snapshot(client):
    with client.app.state.engine.connect() as connection:
        return {table: connection.execute(text('SELECT * FROM ' + table + ' ORDER BY id')).all()
                for table in ('institution', 'academic_periods', 'students', 'student_contacts', 'student_academic_placements', 'departments')}


def test_confirm_does_not_accept_operational_payload_or_coerced_consent(client, caplog):
    draft = preview(client)
    before = operational_snapshot(client)
    for body in ({'confirm': True, 'students': ['PRIVATE SENTINEL']}, {'confirm': 'true'}, {'confirm': 1}, {}, {'confirm': False}):
        response = client.post(f"/api/student-imports/{draft['id']}/confirm", json=body)
        assert response.status_code == 422
        assert 'PRIVATE SENTINEL' not in response.text + caplog.text
    assert operational_snapshot(client) == before


def test_rollback_after_multiple_writes_keeps_every_operational_table(client, monkeypatch, caplog):
    from app import import_api
    draft = preview(client, [{}, {'C': '9876543210', 'G': 'Beto'}])
    before = operational_snapshot(client)
    original = import_api._apply_row
    calls = []
    def fail_after_write(*args):
        original(*args)
        args[0].flush()
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError('PRIVATE SENTINEL')
    monkeypatch.setattr(import_api, '_apply_row', fail_after_write)
    response = confirm(client, draft['id'])
    assert response.status_code == 500
    assert 'PRIVATE SENTINEL' not in response.text + caplog.text
    assert operational_snapshot(client) == before
    with client.app.state.session_factory() as session:
        batch = session.get(ImportBatch, draft['id'])
        assert batch.status == 'PREVIEW' and batch.applied_at is None and batch.applied_result is None


def test_concurrent_confirmation_of_same_id_has_one_effect(client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    draft = preview(client)
    barrier = Barrier(2)
    def execute():
        barrier.wait(timeout=5)
        return confirm(client, draft['id'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: execute(), range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    with client.app.state.session_factory() as session:
        assert count(session, Student) == count(session, StudentAcademicPlacement) == 1


def test_concurrent_distinct_previews_serialize_and_reject_stale(client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    drafts = [preview(client), preview(client)]
    barrier = Barrier(2)
    def execute(draft):
        barrier.wait(timeout=5)
        return confirm(client, draft['id'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(execute, drafts))
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert next(r for r in responses if r.status_code == 409).json()['detail']['code'] == 'PREVIEW_OBSOLETO'
    with client.app.state.session_factory() as session:
        assert count(session, Student) == 1


def test_department_availability_does_not_invalidate_preview(client):
    draft = preview(client)
    assert client.put('/api/departments/1/availability', json={'availability': 'NO_DISPONIBLE'}).status_code == 200
    assert confirm(client, draft['id']).status_code == 200
    assert client.get('/api/departments').json()[0]['availability'] == 'NO_DISPONIBLE'


def test_expired_preview_cannot_apply(client, monkeypatch):
    from app import import_api
    draft = preview(client)
    with client.app.state.session_factory() as session:
        expiry = session.get(ImportBatch, draft['id']).expires_at
    monkeypatch.setattr(import_api, 'utcnow', lambda: expiry)
    before = operational_snapshot(client)
    assert confirm(client, draft['id']).status_code == 410
    assert operational_snapshot(client) == before


def test_expiry_during_valid_application_does_not_revoke_commit(client, monkeypatch):
    from app import import_api
    draft = preview(client)
    with client.app.state.session_factory() as session:
        expiry = session.get(ImportBatch, draft['id']).expires_at
    time = [expiry - timedelta(microseconds=1)]
    monkeypatch.setattr(import_api, 'utcnow', lambda: time[0])
    original = import_api._apply_row
    def advance(*args):
        time[0] = expiry + timedelta(seconds=1)
        return original(*args)
    monkeypatch.setattr(import_api, '_apply_row', advance)
    assert confirm(client, draft['id']).status_code == 200
    assert client.get(f"/api/student-imports/{draft['id']}").json()['status'] == 'APPLIED'


def test_period_versions_and_identical_reimport_are_stable(client):
    draft = preview(client)
    assert confirm(client, draft['id']).status_code == 200
    changed = preview(client, [{'I': 'Octavo', 'J': 'B'}])
    assert changed['counts']['ACTUALIZACION'] == 1
    assert confirm(client, changed['id']).status_code == 200
    with client.app.state.session_factory() as session:
        versions = list(session.scalars(select(StudentAcademicPlacement).order_by(StudentAcademicPlacement.id)))
        assert len(versions) == 2 and versions[0].recorded_to is not None and versions[1].recorded_to is None
        assert versions[0].recorded_to == versions[1].recorded_from
    same = preview(client, [{'I': 'Octavo', 'J': 'B'}])
    before = operational_snapshot(client)
    assert same['counts']['SIN_CAMBIOS'] == 1
    assert confirm(client, same['id']).status_code == 200
    assert operational_snapshot(client) == before


def test_new_period_requires_acceptance_and_preserves_history(client):
    first = preview(client)
    assert confirm(client, first['id']).status_code == 200
    book = workbook([{'I': 'Octavo'}]); book.active['B3'] = 'Año Lectivo 2027 - 2028'
    response = upload(client, binary(book))
    assert response.status_code == 201
    draft = response.json()
    before = operational_snapshot(client)
    assert confirm(client, draft['id'], accept=False).status_code == 409
    assert operational_snapshot(client) == before
    assert confirm(client, draft['id']).status_code == 200
    with client.app.state.session_factory() as session:
        placements = list(session.scalars(select(StudentAcademicPlacement)))
        assert len(placements) == 2 and len({p.academic_period_id for p in placements}) == 2
        assert all(p.recorded_to is None for p in placements)
        active = session.get(AcademicPeriod, session.get(Institution, 1).active_academic_period_id)
        assert active.period_key == '2027-2028'


@pytest.mark.parametrize('scope', ['PADRON_COMPLETO', 'SUBCONJUNTO'])
def test_absences_never_change_absent_student_or_history(client, scope):
    initial = preview(client, [{}, {'C': '9876543210', 'G': 'Beto'}])
    assert confirm(client, initial['id']).status_code == 200
    draft = preview(client, [{}], scope)
    before = operational_snapshot(client)
    assert draft['absence_count'] == (1 if scope == 'PADRON_COMPLETO' else 0)
    assert confirm(client, draft['id']).status_code == 200
    assert operational_snapshot(client) == before


def test_response_lost_after_commit_is_recoverable_and_repeat_safe(client, monkeypatch):
    from app import import_api
    draft = preview(client)
    original = import_api._receipt
    monkeypatch.setattr(import_api, '_receipt', lambda batch: (_ for _ in ()).throw(RuntimeError('simulated lost response')))
    assert confirm(client, draft['id']).status_code == 500
    recovered = client.get(f"/api/student-imports/{draft['id']}")
    assert recovered.json()['status'] == 'APPLIED'
    before = operational_snapshot(client)
    monkeypatch.setattr(import_api, '_receipt', original)
    assert confirm(client, draft['id']).json() == recovered.json()
    assert operational_snapshot(client) == before


@pytest.mark.parametrize('mutation', ['payload', 'category', 'counts', 'missing_row'])
def test_corrupt_preview_is_not_applied(client, mutation):
    draft = preview(client)
    with client.app.state.session_factory() as session:
        batch = session.get(ImportBatch, draft['id'])
        row = session.scalar(select(ImportRow).where(ImportRow.batch_id == batch.id))
        if mutation == 'payload': row.payload = {**row.payload, 'blocking_review_reasons': ['injected blocker']}
        elif mutation == 'category': row.category = 'SIN_CAMBIOS'
        elif mutation == 'counts': batch.proposal = {**batch.proposal, 'counts': {'NUEVO': 900}}
        else: session.delete(row)
        session.commit()
    before = operational_snapshot(client)
    assert confirm(client, draft['id']).status_code == 409
    assert operational_snapshot(client) == before


def test_contact_update_preserves_manual_base_and_noops_after_reimport(client):
    first = preview(client, [{'N': 'Familiar', 'L': 'Ejemplo', 'O': 'Base', 'P': '011111', 'Q': '022222'}])
    assert confirm(client, first['id']).status_code == 200
    with client.app.state.session_factory() as session:
        contact = session.scalar(select(StudentContact))
        contact.home_phone = 'Manual'; contact.manual_protected_fields = ['home_phone']; session.commit()
    incoming = [{'N': 'Familiar', 'L': 'Ejemplo', 'O': '-', 'P': None, 'Q': '033333'}]
    second = preview(client, incoming)
    assert second['counts']['ACTUALIZACION'] == 1
    assert confirm(client, second['id']).status_code == 200
    with client.app.state.session_factory() as session:
        contact = session.scalar(select(StudentContact))
        assert contact.home_phone == 'Manual' and contact.source_baseline['home_phone'] == '011111'
        assert contact.middle_name == 'Base' and contact.source_baseline['middle_name'] == 'Base'
        assert contact.mobile_phone == contact.source_baseline['mobile_phone'] == '033333'
    same = preview(client, incoming)
    assert same['counts']['SIN_CAMBIOS'] == 1
    before = operational_snapshot(client)
    assert confirm(client, same['id']).status_code == 200
    assert operational_snapshot(client) == before


def test_expiry_is_checked_after_waiting_for_writer(client, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from sqlalchemy import event
    from app import import_api
    draft = preview(client)
    with client.app.state.session_factory() as session:
        expiry = session.get(ImportBatch, draft['id']).expires_at
    clock = [expiry - timedelta(seconds=1)]
    monkeypatch.setattr(import_api, 'utcnow', lambda: clock[0])
    attempting = Event()
    def before_execute(conn, cursor, statement, parameters, context, executemany):
        if statement == 'BEGIN IMMEDIATE':
            attempting.set()
    engine = client.app.state.engine
    before = operational_snapshot(client)
    with engine.connect().execution_options(sqlite_write=True) as holder:
        holder.begin()
        event.listen(engine, 'before_cursor_execute', before_execute)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(confirm, client, draft['id'])
                try:
                    assert attempting.wait(timeout=5)
                    clock[0] = expiry
                finally:
                    holder.rollback()
                result = pending.result(timeout=10)
        finally:
            event.remove(engine, 'before_cursor_execute', before_execute)
    assert result.status_code == 410
    assert operational_snapshot(client) == before


def test_busy_writer_returns_retryable_domain_error(client):
    draft = preview(client)
    before = operational_snapshot(client)
    with client.app.state.engine.connect().execution_options(sqlite_write=True) as holder:
        holder.begin()
        response = confirm(client, draft['id'])
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'BASE_OCUPADA'
    assert operational_snapshot(client) == before


def test_placement_preserves_protected_field_and_advances_only_excel_field(client):
    first = preview(client)
    assert confirm(client, first['id']).status_code == 200
    with client.app.state.session_factory() as session:
        placement = session.scalar(select(StudentAcademicPlacement))
        placement.course = 'Manual'
        placement.manual_protected_fields = ['course']
        session.commit()
    second = preview(client, [{'I': 'Octavo', 'J': 'B'}])
    assert second['counts']['ACTUALIZACION'] == 1
    assert confirm(client, second['id']).status_code == 200
    with client.app.state.session_factory() as session:
        placement = session.scalar(select(StudentAcademicPlacement).where(StudentAcademicPlacement.recorded_to.is_(None)))
        assert placement.course == 'Manual' and placement.parallel == 'B'
        assert placement.source_baseline == {'course': 'Séptimo', 'parallel': 'B'}
        assert placement.manual_protected_fields == ['course']
    same = preview(client, [{'I': 'Octavo', 'J': 'B'}])
    before = operational_snapshot(client)
    assert same['counts']['SIN_CAMBIOS'] == 1
    assert confirm(client, same['id']).status_code == 200
    assert operational_snapshot(client) == before


def test_contacts_remain_separate_across_students_and_roles(client):
    contact = {'N': 'Familiar', 'L': 'Ejemplo', 'Q': '011111', 'T': 'Familiar', 'R': 'Ejemplo', 'W': '011111'}
    draft = preview(client, [contact, {**contact, 'C': '9876543210', 'G': 'Beto'}])
    assert confirm(client, draft['id']).status_code == 200
    with client.app.state.session_factory() as session:
        contacts = list(session.scalars(select(StudentContact)))
        assert len(contacts) == 4
        assert len({(c.student_id, c.type) for c in contacts}) == 4
    same = preview(client, [contact, {**contact, 'C': '9876543210', 'G': 'Beto'}])
    before = operational_snapshot(client)
    assert same['counts']['SIN_CAMBIOS'] == 2
    assert confirm(client, same['id']).status_code == 200
    assert operational_snapshot(client) == before


@pytest.mark.parametrize('expired', [False, True])
def test_restarted_backend_recovers_applied_receipt_even_after_purge(client, expired):
    from fastapi.testclient import TestClient
    from app.main import create_app
    draft = preview(client)
    receipt = confirm(client, draft['id']).json()['applied_receipt']
    if expired:
        with client.app.state.session_factory() as session:
            batch = session.get(ImportBatch, draft['id'])
            batch.created_at = utcnow() - timedelta(days=2)
            batch.expires_at = batch.created_at + timedelta(hours=24)
            session.commit()
    before = operational_snapshot(client)
    with TestClient(create_app(client.app.state.settings)) as restarted:
        result = restarted.get(f"/api/student-imports/{draft['id']}")
        assert result.status_code == 200 and result.json()['applied_receipt'] == receipt
        assert confirm(restarted, draft['id']).json()['applied_receipt'] == receipt
        with restarted.app.state.session_factory() as session:
            batch = session.get(ImportBatch, draft['id'])
            assert (batch.proposal is None) == expired
            assert count(session, ImportRow) == (0 if expired else 1)
    assert operational_snapshot(client) == before


def test_existing_institution_without_period_can_be_explicitly_configured(client):
    with client.app.state.session_factory() as session:
        session.add(Institution(id=1, name='Colegio de prueba'))
        session.commit()
    draft = preview(client)
    assert draft['configuration']['requires_acceptance'] is True
    assert draft['configuration']['action'] == 'CREATE_PERIOD_AND_ACTIVATE'
    before = operational_snapshot(client)
    assert confirm(client, draft['id'], accept=False).status_code == 409
    assert operational_snapshot(client) == before
    assert confirm(client, draft['id'], accept=True).status_code == 200
