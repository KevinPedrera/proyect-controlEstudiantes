"""Consultas y escrituras transaccionales; no realizan comunicación de red."""

from sqlalchemy import case, select
from sqlalchemy.orm import sessionmaker

from app.models import Department
from app.schemas import Availability, DepartmentResponse
from app.movements import MovementError, department_counts


class DepartmentNotFound(Exception):
    pass


class DepartmentInactive(Exception):
    pass


def list_departments(factory: sessionmaker) -> list[DepartmentResponse]:
    order = case({"INSPECCION": 0, "DECE": 1, "SALUD": 2}, value=Department.group)
    with factory() as session:
        return [
            DepartmentResponse.model_validate(department)
            for department in session.scalars(select(Department).order_by(order, Department.id))
        ]


def set_availability(
    factory: sessionmaker, department_id: int, availability: Availability, confirmed_active_counts=None
) -> tuple[DepartmentResponse, bool]:
    with factory() as session:
        # Acquire the writer before reading: simultaneous requests cannot decide
        # against the same stale value. Commit releases it before notification.
        session.connection(execution_options={"sqlite_write": True})
        department = session.get(Department, department_id)
        if department is None:
            raise DepartmentNotFound
        if not department.active:
            raise DepartmentInactive
        changed = department.availability != availability
        if changed and availability == 'NO_DISPONIBLE':
            counts = department_counts(session, department_id)
            if counts != confirmed_active_counts and (sum(counts.values()) or confirmed_active_counts is not None):
                raise MovementError('CONFIRMAR_ACTIVOS',
                    'Este departamento tiene estudiantes activos. Podrán continuar, pero no ingresarán nuevos estudiantes.',
                    active_counts=counts)
        if changed:
            department.availability = availability
        result = DepartmentResponse.model_validate(department)
        try:
            session.commit()
        except Exception:
            # An error raised while committing can leave the pooled SQLite
            # connection in a transaction. Roll it back before it is reused.
            session.rollback()
            raise
        return result, changed
