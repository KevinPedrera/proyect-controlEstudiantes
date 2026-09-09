"""Reglas de candidatos reutilizables; comparan, nunca vinculan ni actualizan."""

from collections import Counter, defaultdict
import hashlib
import json
import re

from sqlalchemy import select

from app.import_parser import NAME_FIELDS, STUDENT_FIELDS, comparison_key
from app.student_models import AcademicPeriod, Institution, Student, StudentAcademicPlacement, StudentContact

CONTACT_FIELDS = ('type', 'relationship', *NAME_FIELDS, 'home_phone', 'mobile_phone', 'work_phone')


def name_key(person: dict) -> tuple:
    return tuple(comparison_key(person.get(field)) for field in NAME_FIELDS)


def document_key(person: dict) -> str:
    value = comparison_key(person.get('document'))
    # A literal placeholder is evidence, never a shared identity signal.
    return '' if value == '-' else value


def usable_document(person: dict) -> bool:
    value = person.get('document') or ''
    kind = comparison_key(person.get('document_type'))
    # Structural eligibility only; no claim of authenticated identity.
    if kind == 'cédula':
        return bool(re.fullmatch(r'\d{10}', value))
    if kind == 'pasaporte':
        return bool(re.fullmatch(r'[A-Za-z0-9]{5,30}', value))
    return False


def find_candidates(incoming: dict, existing: list[dict]) -> list[dict]:
    """Nombres/documentos son señales, no claves únicas de identidad."""
    result = []
    for person in existing:
        reasons = []
        if document_key(incoming) and document_key(incoming) == document_key(person):
            reasons.append('DOCUMENTO_COINCIDENTE')
        if name_key(incoming) == name_key(person) and incoming.get('first_name') and incoming.get('last_name'):
            reasons.append('NOMBRE_COMPLETO_COINCIDENTE')
        elif all(incoming.get(f) and comparison_key(incoming[f]) == comparison_key(person.get(f)) for f in ('first_name', 'last_name')):
            reasons.append('POSIBLE_COINCIDENCIA_NOMBRE_APELLIDO')
        if reasons:
            result.append({'student_id': person['id'], 'name': ' '.join(person[f] for f in NAME_FIELDS if person.get(f)), 'course': person.get('course'), 'parallel': person.get('parallel'), 'reasons': reasons})
    return result


def _snapshot(session, period_key: str):
    tables = (Institution, AcademicPeriod, Student, StudentAcademicPlacement, StudentContact)
    raw = {model.__tablename__: [{c.name: getattr(item, c.name) for c in model.__table__.columns} for item in session.scalars(select(model).order_by(model.id))] for model in tables}
    revision = hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()
    periods = raw['academic_periods']
    period = next((p for p in periods if p['period_key'] == period_key), None)
    placements = {p['student_id']: p for p in raw['student_academic_placements'] if period and p['academic_period_id'] == period['id'] and p['recorded_to'] is None}
    people = []
    for student in raw['students']:
        placement = placements.get(student['id'], {})
        contacts = [{f: c[f] for f in CONTACT_FIELDS} for c in raw['student_contacts'] if c['student_id'] == student['id'] and c['active']]
        people.append({**student, 'course': placement.get('course'), 'parallel': placement.get('parallel'), 'contacts': contacts})
    return raw['institution'], people, placements, revision


def _contact_signature(contacts):
    return sorted(json.dumps({k: c.get(k) for k in CONTACT_FIELDS}, sort_keys=True, ensure_ascii=False) for c in contacts)


def _differences(incoming, existing):
    differences, tags = [], set()
    for field in STUDENT_FIELDS:
        old, new = existing.get(field), incoming['student'].get(field)
        if old != new:
            tag = 'DOCUMENTO' if field in ('document', 'document_type') else 'CURSO' if field == 'course' else 'PARALELO' if field == 'parallel' else 'DATOS_PERSONALES'
            action = 'CONSERVAR_ACTUAL' if new is None else 'REVISAR_GUION' if new == '-' else 'PROPONER_NUEVA_VERSION' if field in ('course', 'parallel') else 'PROPONER_ACTUALIZACION'
            differences.append({'field': field, 'current': old, 'incoming': new, 'action': action})
            if new is not None:
                tags.add(tag)
    if _contact_signature(incoming['contacts']) != _contact_signature(existing['contacts']):
        differences.append({'field': 'contacts', 'current': existing['contacts'], 'incoming': incoming['contacts'], 'action': 'REVISAR_CONTACTOS_SIN_BORRAR_VACIOS'})
        # No contact is replaced or matched by position in a preview.
        tags.add('CONTACTOS')
    return differences, sorted(tags)


def compare_import(session, parsed, scope: str) -> dict:
    institutions, people, placements, revision = _snapshot(session, parsed.period_key)
    warnings = []
    institution_conflict = bool(institutions and comparison_key(institutions[0]['name']) != comparison_key(parsed.institution))
    if institution_conflict:
        warnings.append('La institución difiere de la registrada. Requiere revisión; no se modifica.')
    documents = Counter(document_key(r['student']) for r in parsed.rows if document_key(r['student']))
    names = Counter(name_key(r['student']) for r in parsed.rows if r['student'].get('first_name') and r['student'].get('last_name'))
    targeted = defaultdict(list)
    result = []
    for original in parsed.rows:
        blocking_review_reasons = []
        row = {**original, 'warnings': list(original['warnings']), 'blocking_review_reasons': blocking_review_reasons, 'conflicts': blocking_review_reasons, 'differences': [], 'tags': []}
        student = row['student']
        candidates = find_candidates(student, people)
        row['candidates'] = candidates
        for candidate in candidates:
            targeted[candidate['student_id']].append(row)
        if student.get('document') and not usable_document(student):
            row['warnings'].append({'code': 'DOCUMENT_REVIEW', 'cell': str(row['row_number']), 'message': 'Documento o tipo no utilizable para correspondencia fuerte.'})
        if documents[document_key(student)] > 1 or names[name_key(student)] > 1:
            blocking_review_reasons.append('Posible duplicado dentro del archivo; no se fusiona.')
        if row['errors'] or institution_conflict:
            blocking_review_reasons.append('Datos mínimos o institución requieren revisión.')
        strong = False
        if len(candidates) == 1:
            existing = next(p for p in people if p['id'] == candidates[0]['student_id'])
            strong = (usable_document(student) and usable_document(existing) and document_key(student) == document_key(existing) and name_key(student) == name_key(existing) and comparison_key(student.get('document_type')) == comparison_key(existing.get('document_type')))
            row['differences'], row['tags'] = _differences(row, existing)
        if candidates and not strong:
            blocking_review_reasons.append('Correspondencia pendiente de resolución humana.')
        # Quality evidence never determines the action by itself.
        needs_review = bool(blocking_review_reasons)
        row['category'] = 'REQUIERE_REVISION' if needs_review else ('ACTUALIZACION' if row['tags'] else 'SIN_CAMBIOS') if strong else 'NUEVO'
        result.append(row)
    for rows in targeted.values():
        if len(rows) > 1:
            for row in rows:
                row['category'] = 'REQUIERE_REVISION'
                row['blocking_review_reasons'].append('Varias filas proponen el mismo estudiante; no se vinculan.')
    # Any unresolved identity/incomplete row can hide an existing person.
    absence_reliable = scope == 'PADRON_COMPLETO' and not institution_conflict and not any(r['blocking_review_reasons'] for r in result)
    absences = []
    if absence_reliable:
        for person in people:
            if person['id'] in placements and person['id'] not in targeted:
                absences.append({'student_id': person['id'], 'name': ' '.join(person[f] for f in NAME_FIELDS if person.get(f)), 'course': person['course'], 'parallel': person['parallel']})
    elif scope == 'PADRON_COMPLETO':
        warnings.append('Ausencias no concluyentes: hay identidades o filas pendientes de revisión.')
    counts = {key: 0 for key in ('NUEVO', 'SIN_CAMBIOS', 'ACTUALIZACION', 'REQUIERE_REVISION')}
    counts.update(Counter(row['category'] for row in result))
    return {'institution': parsed.institution, 'academic_period': parsed.period, 'period_key': parsed.period_key, 'sheet': parsed.sheet, 'emergency_blocks': 2, 'total': len(result), 'counts': counts, 'warnings': warnings, 'quality_warning_count': sum(len(r['warnings']) for r in result), 'rows_with_warnings': sum(bool(r['warnings']) for r in result), 'rows_with_blocking_reasons': sum(bool(r['blocking_review_reasons']) for r in result), 'skipped_empty_rows': parsed.skipped_empty_rows, 'snapshot_revision': revision, 'absences_calculated': absence_reliable, 'absences': absences, 'rows': result}
