"""Read-only comparison that stores only safe, effective application plans."""

from collections import Counter, defaultdict
import hashlib
import json
import re

from sqlalchemy import select

from app.import_parser import NAME_FIELDS, STUDENT_FIELDS, comparison_key
from app.student_models import AcademicPeriod, Institution, Student, StudentAcademicPlacement, StudentContact

APPLICATION_CONTRACT_VERSION = "3B-1"
CONTACT_FIELDS = ("type", "relationship", *NAME_FIELDS, "home_phone", "mobile_phone", "work_phone")
STUDENT_VALUE_FIELDS = ("document", "document_type", "last_name", "second_last_name", "first_name", "middle_name")
CONTACT_VALUE_FIELDS = ("relationship", *NAME_FIELDS, "home_phone", "mobile_phone", "work_phone")


def name_key(person: dict) -> tuple[str, ...]:
    return tuple(comparison_key(person.get(field)) for field in NAME_FIELDS)


def document_key(person: dict) -> str:
    value = comparison_key(person.get("document"))
    return "" if value == "-" else value


def usable_document(person: dict) -> bool:
    value, kind = person.get("document") or "", comparison_key(person.get("document_type"))
    if kind == "cédula":
        return bool(re.fullmatch(r"\d{10}", value))
    if kind == "pasaporte":
        return bool(re.fullmatch(r"[A-Za-z0-9]{5,30}", value))
    return False


def _name_compatible(incoming: dict, existing: dict) -> bool:
    """Required names identify; omitted optional names do not break a match."""
    for field in ("first_name", "last_name"):
        if comparison_key(incoming.get(field)) != comparison_key(existing.get(field)):
            return False
    for field in ("middle_name", "second_last_name"):
        new, old = incoming.get(field), existing.get(field)
        if new not in (None, "-") and old not in (None, "-") and comparison_key(new) != comparison_key(old):
            return False
    return True


def _candidate(person: dict, reasons: list[str]) -> dict:
    return {
        "student_id": person["id"],
        "name": " ".join(person[field] for field in NAME_FIELDS if person.get(field)),
        "course": person.get("course"),
        "parallel": person.get("parallel"),
        "reasons": reasons,
    }


def find_candidates(incoming: dict, existing: list[dict]) -> list[dict]:
    result = []
    for person in existing:
        reasons = []
        if document_key(incoming) and document_key(incoming) == document_key(person):
            reasons.append("DOCUMENTO_COINCIDENTE")
        if name_key(incoming) == name_key(person) and incoming.get("first_name") and incoming.get("last_name"):
            reasons.append("NOMBRE_COMPLETO_COINCIDENTE")
        elif all(incoming.get(field) and comparison_key(incoming[field]) == comparison_key(person.get(field)) for field in ("first_name", "last_name")):
            reasons.append("POSIBLE_COINCIDENCIA_NOMBRE_APELLIDO")
        if reasons:
            result.append(_candidate(person, reasons))
    return result


def _snapshot(session, period_key: str):
    tables = (Institution, AcademicPeriod, Student, StudentAcademicPlacement, StudentContact)
    raw = {
        model.__tablename__: [{column.name: getattr(item, column.name) for column in model.__table__.columns} for item in session.scalars(select(model).order_by(model.id))]
        for model in tables
    }
    revision = hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()
    period = next((item for item in raw["academic_periods"] if item["period_key"] == period_key), None)
    placements = {
        item["student_id"]: item
        for item in raw["student_academic_placements"]
        if period and item["academic_period_id"] == period["id"] and item["recorded_to"] is None
    }
    people = []
    for student in raw["students"]:
        placement = placements.get(student["id"])
        contacts = [
            {
                **{field: item[field] for field in CONTACT_FIELDS},
                "id": item["id"],
                "source_baseline": item.get("source_baseline"),
                "manual_protected_fields": item.get("manual_protected_fields") or [],
            }
            for item in raw["student_contacts"]
            if item["student_id"] == student["id"] and item["active"]
        ]
        people.append({**student, "course": placement.get("course") if placement else None, "parallel": placement.get("parallel") if placement else None, "placement": placement, "contacts": contacts})
    return raw["institution"], people, placements, revision


def snapshot_revision(session, period_key: str) -> str:
    return _snapshot(session, period_key)[3]


def _strong_candidates(incoming: dict, people: list[dict]) -> list[dict]:
    return [
        person for person in people
        if usable_document(incoming)
        and usable_document(person)
        and document_key(incoming) == document_key(person)
        and comparison_key(incoming.get("document_type")) == comparison_key(person.get("document_type"))
        and _name_compatible(incoming, person)
    ]


def _safe_weak_competitor(incoming: dict, person: dict) -> bool:
    return usable_document(person) and document_key(incoming) != document_key(person) and not _name_compatible(incoming, person)


def _effective_value(old, incoming, protected: set[str], baseline: dict | None, field: str):
    """Return final field value, effective change, and whether authority is unknown."""
    if field in protected or incoming is None or (incoming == "-" and old not in (None, "", "-")):
        return old, False, False
    if old == incoming:
        return old, False, False
    if not isinstance(baseline, dict) or field not in baseline:
        return old, False, True
    # BASE divergence is conservative future-manual protection even before a UI exists.
    if baseline.get(field) != old:
        return old, False, False
    return incoming, True, False


def _student_plan(row: dict, existing: dict | None):
    incoming = row["student"]
    if existing is None:
        return {
            "action": "CREATE",
            "student_id": None,
            "values": {field: incoming.get(field) for field in STUDENT_VALUE_FIELDS},
            "placement": {"action": "CREATE", "course": incoming["course"], "parallel": incoming["parallel"]},
        }, [], [], []
    differences, tags, blockers = [], set(), []
    # Identity is deliberately never updated automatically, even for Excel BASE.
    for field in STUDENT_VALUE_FIELDS:
        old, new = existing.get(field), incoming.get(field)
        if new is not None and not (new == "-" and old not in (None, "", "-")) and old != new:
            differences.append({"field": field, "current": old, "incoming": new, "action": "REQUIERE_REVISION_IDENTIDAD"})
            tags.add("DOCUMENTO" if field.startswith("document") else "DATOS_PERSONALES")
            blockers.append("Cambio de identidad no asociable con seguridad.")
    placement = existing.get("placement")
    placement_plan = {"action": "NOOP", "course": existing.get("course"), "parallel": existing.get("parallel")}
    if not blockers and (incoming["course"] != existing.get("course") or incoming["parallel"] != existing.get("parallel")):
        if placement is None:
            if not isinstance(existing.get("source_baseline"), dict):
                blockers.append("La procedencia del estudiante es desconocida; no se crea ubicación automáticamente.")
            else:
                placement_plan = {"action": "CREATE", "course": incoming["course"], "parallel": incoming["parallel"]}
                for field in ("course", "parallel"):
                    differences.append({"field": field, "current": None, "incoming": incoming[field], "action": "PROPONER_NUEVA_VERSION"})
                tags.update(("CURSO", "PARALELO"))
            return {"action": "UPDATE" if not blockers else "NOOP", "student_id": existing["id"], "values": {field: existing.get(field) for field in STUDENT_VALUE_FIELDS}, "placement": placement_plan}, differences, sorted(tags), blockers
        protected = set((placement or {}).get("manual_protected_fields") or [])
        baseline = (placement or {}).get("source_baseline")
        final = {"course": existing.get("course"), "parallel": existing.get("parallel")}
        unknown = False
        for field in ("course", "parallel"):
            value, changed, field_unknown = _effective_value(existing.get(field), incoming[field], protected, baseline, field)
            final[field], unknown = value, unknown or field_unknown
            if changed:
                differences.append({"field": field, "current": existing.get(field), "incoming": incoming[field], "action": "PROPONER_NUEVA_VERSION"})
                tags.add("CURSO" if field == "course" else "PARALELO")
        if unknown:
            blockers.append("La procedencia de la ubicación es desconocida; no se actualiza automáticamente.")
        elif differences:
            action = "REPLACE" if placement is not None else "CREATE"
            placement_plan = {"action": action, **final}
    return {"action": "UPDATE" if differences and not blockers else "NOOP", "student_id": existing["id"], "values": {field: existing.get(field) for field in STUDENT_VALUE_FIELDS}, "placement": placement_plan}, differences, sorted(tags), blockers


def _contact_exact_after_preservation(incoming: dict, existing: dict) -> bool:
    for field in CONTACT_VALUE_FIELDS:
        old, new = existing.get(field), incoming.get(field)
        effective = old if new is None or (new == "-" and old not in (None, "", "-")) else new
        if effective != old:
            return False
    return True


def _contact_identity_match(incoming: dict, existing: dict) -> bool:
    # An incomplete contact has no reliable identity other than being identical.
    if not incoming.get("first_name") or not incoming.get("last_name"):
        return False
    if not existing.get("first_name") or not existing.get("last_name"):
        return False
    for field in NAME_FIELDS:
        new, old = incoming.get(field), existing.get(field)
        # An absent or literal-dash optional component is preserved, not treated as
        # proof that this is another person. A supplied conflicting component is.
        if field in ("middle_name", "second_last_name") and new in (None, "-"):
            continue
        if comparison_key(new) != comparison_key(old):
            return False
    return True


def _contact_plan(incoming_contacts: list[dict], existing_contacts: list[dict]):
    plans, differences, blockers, unmatched = [], [], [], list(existing_contacts)
    for incoming in incoming_contacts:
        same_role = [contact for contact in unmatched if contact["type"] == incoming["type"]]
        exact = [contact for contact in same_role if _contact_exact_after_preservation(incoming, contact)]
        identified = [contact for contact in same_role if _contact_identity_match(incoming, contact)]
        # Identical duplicate emergency contacts remain distinct records. Matching
        # them one-to-one in a stable order preserves a reimport without merging.
        chosen = exact[0] if exact else identified[0] if len(identified) == 1 else None
        if chosen is None and same_role:
            blockers.append("Contacto existente no puede asociarse con seguridad; no se reemplaza.")
            continue
        if chosen is None:
            plans.append({"action": "CREATE", "contact_id": None, "values": {field: incoming.get(field) for field in CONTACT_FIELDS}})
            continue
        unmatched.remove(chosen)
        protected, baseline, values, changed, unknown = set(chosen.get("manual_protected_fields") or []), chosen.get("source_baseline"), {}, False, False
        for field in CONTACT_VALUE_FIELDS:
            value, field_changed, field_unknown = _effective_value(chosen.get(field), incoming.get(field), protected, baseline, field)
            values[field], changed, unknown = value, changed or field_changed, unknown or field_unknown
        if unknown:
            blockers.append("La procedencia del contacto es desconocida; no se actualiza automáticamente.")
        if changed:
            differences.append({
                "field": "contacts",
                "contact_id": chosen["id"],
                "current": {field: chosen.get(field) for field in CONTACT_VALUE_FIELDS},
                "incoming": values,
                "action": "PROPONER_ACTUALIZACION",
            })
        plans.append({"action": "UPDATE" if changed and not unknown else "NOOP", "contact_id": chosen["id"], "values": {"type": chosen["type"], **values}})
    # unmatched contacts remain active. Missing blocks never imply a deletion.
    return plans, differences, blockers


def _configuration(institutions: list[dict], period_key: str, institution: str, period: str) -> dict:
    if institutions and comparison_key(institutions[0]["name"]) != comparison_key(institution):
        action, accept = "INCOMPATIBLE", False
    else:
        action, accept = ("INITIALIZE", True) if not institutions else ("NONE", False)
    return {"action": action, "requires_acceptance": accept, "institution": institution, "academic_period": {"label": period, "period_key": period_key}}


def compare_import(session, parsed, scope: str) -> dict:
    institutions, people, placements, revision = _snapshot(session, parsed.period_key)
    configuration = _configuration(institutions, parsed.period_key, parsed.institution, parsed.period)
    institution_conflict = configuration["action"] == "INCOMPATIBLE"
    documents = Counter(document_key(row["student"]) for row in parsed.rows if document_key(row["student"]))
    names = Counter(name_key(row["student"]) for row in parsed.rows if row["student"].get("first_name") and row["student"].get("last_name"))
    targeted, result = defaultdict(list), []
    for original in parsed.rows:
        blockers: list[str] = []
        row = {**original, "warnings": list(original["warnings"]), "blocking_review_reasons": blockers, "conflicts": blockers, "differences": [], "tags": []}
        student = row["student"]
        candidates, strong = find_candidates(student, people), _strong_candidates(student, people)
        row["candidates"] = candidates
        if student.get("document") and not usable_document(student):
            row["warnings"].append({"code": "DOCUMENT_REVIEW", "cell": str(row["row_number"]), "message": "Documento o tipo no utilizable para correspondencia fuerte."})
        if documents[document_key(student)] > 1 or names[name_key(student)] > 1:
            blockers.append("Posible duplicado dentro del archivo; no se fusiona.")
        if row["errors"]:
            blockers.append("Datos mínimos requieren revisión.")
        if institution_conflict:
            blockers.append("La institución no coincide con la registrada.")
        existing = None
        informational_differences, informational_tags = [], []
        if len(strong) == 1:
            existing = strong[0]
            targeted[existing["id"]].append(row)
            if not existing.get("active"):
                blockers.append("El estudiante coincidente está inactivo; no se reactiva automáticamente.")
            competing = [person for person in people if person["id"] != existing["id"] and not _safe_weak_competitor(student, person)]
            if any(person["id"] in {candidate["student_id"] for candidate in candidates} for person in competing):
                blockers.append("Existe una coincidencia de identidad contradictoria.")
        elif len(strong) > 1:
            blockers.append("Documento e identidad coinciden con más de un estudiante.")
        elif candidates:
            blockers.append("Correspondencia pendiente de resolución humana.")
            # Keep the rejected evidence visible without turning it into an
            # application plan or implying that the candidate was selected.
            if len(candidates) == 1:
                candidate = next(person for person in people if person["id"] == candidates[0]["student_id"])
                for field in STUDENT_VALUE_FIELDS:
                    if student.get(field) != candidate.get(field):
                        informational_differences.append({"field": field, "current": candidate.get(field), "incoming": student.get(field), "action": "REQUIERE_REVISION_IDENTIDAD"})
                        informational_tags.append("DOCUMENTO" if field.startswith("document") else "DATOS_PERSONALES")
        plan, differences, tags, plan_blockers = _student_plan(row, existing)
        blockers.extend(plan_blockers)
        differences.extend(informational_differences)
        tags.extend(informational_tags)
        contact_plans, contact_differences, contact_blockers = _contact_plan(row["contacts"], existing["contacts"] if existing else [])
        blockers.extend(contact_blockers)
        if contact_differences or any(item["action"] == "CREATE" for item in contact_plans):
            tags.append("CONTACTOS")
            differences.extend(contact_differences or [{"field": "contacts", "current": None, "incoming": None, "action": "PROPONER_ACTUALIZACION"}])
        if plan:
            plan["contacts"] = contact_plans
            row["application_plan"] = plan
        row["differences"], row["tags"] = differences, sorted(set(tags))
        row["category"] = "REQUIERE_REVISION" if blockers else "NUEVO" if existing is None else "ACTUALIZACION" if row["tags"] else "SIN_CAMBIOS"
        result.append(row)
    for rows in targeted.values():
        if len(rows) > 1:
            for row in rows:
                row["blocking_review_reasons"].append("Varias filas proponen el mismo estudiante; no se vinculan.")
                row["category"] = "REQUIERE_REVISION"
    absence_reliable = scope == "PADRON_COMPLETO" and not institution_conflict and not any(row["blocking_review_reasons"] for row in result)
    absences = []
    if absence_reliable:
        for person in people:
            if person["id"] in placements and person["id"] not in targeted:
                absences.append({"student_id": person["id"], "name": " ".join(person[field] for field in NAME_FIELDS if person.get(field)), "course": person["course"], "parallel": person["parallel"]})
    warnings = [] if absence_reliable or scope != "PADRON_COMPLETO" else ["Ausencias no concluyentes: hay identidades o filas pendientes de revisión."]
    if institutions and not institution_conflict:
        active = institutions[0].get("active_academic_period_id")
        target = next((period for period in session.scalars(select(AcademicPeriod)) if period.period_key == parsed.period_key), None)
        # No active period and no matching period still requires an explicit setup.
        if target is None or active != target.id:
            configuration["action"], configuration["requires_acceptance"] = ("CREATE_PERIOD_AND_ACTIVATE" if target is None else "ACTIVATE_PERIOD"), True
    counts = {key: 0 for key in ("NUEVO", "SIN_CAMBIOS", "ACTUALIZACION", "REQUIERE_REVISION")}
    counts.update(Counter(row["category"] for row in result))
    return {"institution": parsed.institution, "academic_period": parsed.period, "period_key": parsed.period_key, "sheet": parsed.sheet, "emergency_blocks": 2, "total": len(result), "counts": counts, "warnings": warnings, "quality_warning_count": sum(len(row["warnings"]) for row in result), "rows_with_warnings": sum(bool(row["warnings"]) for row in result), "rows_with_blocking_reasons": sum(bool(row["blocking_review_reasons"]) for row in result), "skipped_empty_rows": parsed.skipped_empty_rows, "snapshot_revision": revision, "absences_calculated": absence_reliable, "absences": absences, "configuration": configuration, "contract_version": APPLICATION_CONTRACT_VERSION, "rows": result}
