"""Focused synthetic tests for the read-only 3B comparison plan."""

from sqlalchemy import select

from app.import_comparison import compare_import
from app.import_parser import ParsedImport
from datetime import timedelta

from app.student_models import AcademicPeriod, ImportBatch, Institution, Student, StudentAcademicPlacement, StudentContact, utcnow


def parsed(rows, period_key="2026-2027"):
    return ParsedImport("Colegio de prueba", f"Año Lectivo {period_key.replace('-', ' - ')}", period_key, "Listado", rows, 0)


def row(**student):
    values = {"document":"0123456789", "document_type":"Cédula", "first_name":"Ana", "middle_name":None, "last_name":"Pérez", "second_last_name":None, "course":"Séptimo", "parallel":"A", **student}
    return {"row_number": 8, "sheet":"Listado", "student":values, "contacts":[], "warnings":[], "errors":[]}


def seed(session, *, document="0123456789", first="Ana", middle=None, last="Pérez", course="Séptimo", parallel="A", baseline=True):
    period = session.scalar(select(AcademicPeriod).where(AcademicPeriod.period_key == "2026-2027"))
    if period is None:
        period = AcademicPeriod(label="Año Lectivo 2026 - 2027", period_key="2026-2027")
        session.add(period); session.flush()
    if baseline and session.get(ImportBatch, "batch-known") is None:
        now = utcnow()
        session.add(ImportBatch(id="batch-known", profile="synthetic", file_hash="0" * 64, scope="SUBCONJUNTO", status="PREVIEW", created_at=now, expires_at=now + timedelta(hours=1), proposal={}))
        session.flush()
    values = {"document":document,"document_type":"Cédula","first_name":first,"middle_name":middle,"last_name":last,"second_last_name":None}
    student = Student(**values, source_batch_id="batch-known" if baseline else None, source_baseline=values if baseline else None)
    session.add(student); session.flush()
    session.add(StudentAcademicPlacement(student_id=student.id, academic_period_id=period.id, course=course, parallel=parallel, source_batch_id="batch-known" if baseline else None))
    session.flush()
    return student


def single(session, **student):
    proposal = compare_import(session, parsed([row(**student)]), "SUBCONJUNTO")
    return proposal["rows"][0]


def test_strong_document_match_discards_only_clearly_other_weak_candidate(client):
    with client.app.state.session_factory() as session:
        seed(session, middle="Correcta")
        seed(session, document="9876543210", middle="Otra")
        session.commit()
        result = single(session, middle_name="Correcta")
    assert result["category"] == "SIN_CAMBIOS"
    assert result["blocking_review_reasons"] == []


def test_document_competitor_is_a_real_identity_conflict(client):
    with client.app.state.session_factory() as session:
        seed(session)
        seed(session, document="0123456789", first="Beto", last="López")
        session.commit()
        result = single(session)
    assert result["category"] == "REQUIERE_REVISION"
    assert result["blocking_review_reasons"]


def test_optional_dash_and_empty_preserve_accepted_contact_values(client):
    with client.app.state.session_factory() as session:
        student = seed(session)
        fields = {"type":"REPRESENTANTE_LEGAL","first_name":"Familiar","last_name":"Uno","middle_name":"Valor","relationship":None,"second_last_name":None,"home_phone":None,"mobile_phone":"0991111111","work_phone":None}
        session.add(StudentContact(student_id=student.id, **fields, source_batch_id="batch-known", source_baseline=fields))
        session.commit()
        incoming = row()
        incoming["contacts"] = [{"type":"REPRESENTANTE_LEGAL","first_name":"Familiar","last_name":"Uno","middle_name":"-","relationship":None,"second_last_name":None,"home_phone":None,"mobile_phone":None,"work_phone":None}]
        result = compare_import(session, parsed([incoming]), "SUBCONJUNTO")["rows"][0]
    assert result["category"] == "SIN_CAMBIOS"
    assert result["application_plan"]["contacts"][0]["values"]["middle_name"] == "Valor"


def test_incomplete_identical_contact_is_noop_but_substitution_blocks(client):
    with client.app.state.session_factory() as session:
        student = seed(session)
        fields = {"type":"MADRE","first_name":"Familiar","last_name":None,"middle_name":None,"relationship":None,"second_last_name":None,"home_phone":None,"mobile_phone":None,"work_phone":None}
        session.add(StudentContact(student_id=student.id, **fields, source_batch_id="batch-known", source_baseline=fields))
        session.commit()
        same = row(); same["contacts"] = [{"type":"MADRE", **{key:value for key,value in fields.items() if key != "type"}}]
        assert compare_import(session, parsed([same]), "SUBCONJUNTO")["rows"][0]["category"] == "SIN_CAMBIOS"
        changed = row(); changed["contacts"] = [{"type":"MADRE","first_name":"Otra","last_name":"Persona","middle_name":None,"relationship":None,"second_last_name":None,"home_phone":None,"mobile_phone":None,"work_phone":None}]
        result = compare_import(session, parsed([changed]), "SUBCONJUNTO")["rows"][0]
    assert result["category"] == "REQUIERE_REVISION"


def test_emergencies_reorder_and_unique_phone_change_do_not_merge(client):
    with client.app.state.session_factory() as session:
        student = seed(session)
        contacts = []
        for first, phone in (("Uno", "0991111111"), ("Dos", "0992222222")):
            fields = {"type":"EMERGENCIA","first_name":first,"last_name":"Familiar","middle_name":None,"relationship":None,"second_last_name":None,"home_phone":None,"mobile_phone":phone,"work_phone":None}
            contacts.append(StudentContact(student_id=student.id, **fields, source_batch_id="batch-known", source_baseline=fields))
        session.add_all(contacts); session.commit()
        incoming = row(); incoming["contacts"] = [
            {"type":"EMERGENCIA","first_name":"Dos","last_name":"Familiar","middle_name":None,"relationship":None,"second_last_name":None,"home_phone":None,"mobile_phone":"0993333333","work_phone":None},
            {"type":"EMERGENCIA","first_name":"Uno","last_name":"Familiar","middle_name":None,"relationship":None,"second_last_name":None,"home_phone":None,"mobile_phone":"0991111111","work_phone":None},
        ]
        result = compare_import(session, parsed([incoming]), "SUBCONJUNTO")["rows"][0]
    assert result["category"] == "ACTUALIZACION"
    plans = result["application_plan"]["contacts"]
    assert len(plans) == 2 and sum(plan["action"] == "UPDATE" for plan in plans) == 1


def test_contact_second_name_conflict_blocks_instead_of_mixing_people(client):
    with client.app.state.session_factory() as session:
        student = seed(session)
        fields = {"type":"REPRESENTANTE_LEGAL","first_name":"Familiar","last_name":"Uno","middle_name":"Alicia","relationship":None,"second_last_name":None,"home_phone":None,"mobile_phone":"0991111111","work_phone":None}
        session.add(StudentContact(student_id=student.id, **fields, source_batch_id="batch-known", source_baseline=fields))
        session.commit()
        incoming = row(); incoming["contacts"] = [{**fields, "middle_name":"Beatriz", "mobile_phone":"0992222222"}]
        result = compare_import(session, parsed([incoming]), "SUBCONJUNTO")["rows"][0]
    assert result["category"] == "REQUIERE_REVISION"
    assert result["blocking_review_reasons"]


def test_identical_emergency_duplicates_reimport_without_block_or_merge(client):
    with client.app.state.session_factory() as session:
        student = seed(session)
        fields = {"type":"EMERGENCIA","first_name":"Igual","last_name":"Contacto","middle_name":None,"relationship":None,"second_last_name":None,"home_phone":None,"mobile_phone":"0991111111","work_phone":None}
        session.add_all([StudentContact(student_id=student.id, **fields, source_batch_id="batch-known", source_baseline=fields) for _ in range(2)])
        session.commit()
        incoming = row(); incoming["contacts"] = [dict(fields), dict(fields)]
        result = compare_import(session, parsed([incoming]), "SUBCONJUNTO")["rows"][0]
    assert result["category"] == "SIN_CAMBIOS"
    assert len(result["application_plan"]["contacts"]) == 2


def test_contact_homonyms_use_all_supplied_name_components(client):
    with client.app.state.session_factory() as session:
        student = seed(session)
        for middle, phone in (("Alba", "0991111111"), ("Bruno", "0992222222")):
            fields = {"type":"EMERGENCIA","first_name":"Alex","last_name":"Paz","middle_name":middle,"relationship":None,"second_last_name":None,"home_phone":None,"mobile_phone":phone,"work_phone":None}
            session.add(StudentContact(student_id=student.id, **fields, source_batch_id="batch-known", source_baseline=fields))
        session.commit()
        incoming = row(); incoming["contacts"] = [
            {"type":"EMERGENCIA","first_name":"Alex","last_name":"Paz","middle_name":"Bruno","relationship":None,"second_last_name":None,"home_phone":None,"mobile_phone":"0993333333","work_phone":None},
            {"type":"EMERGENCIA","first_name":"Alex","last_name":"Paz","middle_name":"Alba","relationship":None,"second_last_name":None,"home_phone":None,"mobile_phone":"0991111111","work_phone":None},
        ]
        result = compare_import(session, parsed([incoming]), "SUBCONJUNTO")["rows"][0]
    assert result["category"] == "ACTUALIZACION"
    change = next(item for item in result["differences"] if item["field"] == "contacts")
    assert change["current"]["middle_name"] == "Bruno"


def test_inactive_student_is_a_blocking_match(client):
    with client.app.state.session_factory() as session:
        student = seed(session); student.active = False; session.commit()
        result = single(session)
    assert result["category"] == "REQUIERE_REVISION"
    assert result["blocking_review_reasons"]


def test_existing_institution_requires_explicit_period_setup_when_no_active_period(client):
    with client.app.state.session_factory() as session:
        session.add(Institution(id=1, name="Colegio de prueba")); session.commit()
        no_period = compare_import(session, parsed([row()]), "SUBCONJUNTO")
        assert no_period["configuration"]["action"] == "CREATE_PERIOD_AND_ACTIVATE"
        assert no_period["configuration"]["requires_acceptance"]
        period = AcademicPeriod(label="Año Lectivo 2026 - 2027", period_key="2026-2027")
        session.add(period); session.commit()
        existing_period = compare_import(session, parsed([row()]), "SUBCONJUNTO")
    assert existing_period["configuration"]["action"] == "ACTIVATE_PERIOD"
    assert existing_period["configuration"]["requires_acceptance"]


def test_unknown_or_protected_provenance_never_creates_effective_update(client):
    with client.app.state.session_factory() as session:
        student = seed(session, baseline=False)
        contact_fields = {"type":"PADRE","first_name":"Familiar","last_name":"Uno","middle_name":None,"relationship":None,"second_last_name":None,"home_phone":None,"mobile_phone":"0991111111","work_phone":None}
        session.add(StudentContact(student_id=student.id, **contact_fields, source_baseline=None))
        session.commit()
        incoming = row(course="Octavo")
        incoming["contacts"] = [{**contact_fields, "mobile_phone":"0992222222"}]
        result = compare_import(session, parsed([incoming]), "SUBCONJUNTO")["rows"][0]
    assert result["category"] == "REQUIERE_REVISION"
    assert result["blocking_review_reasons"]
