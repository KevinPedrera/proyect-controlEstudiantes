"""Transactional movement operations. Notifications belong to the HTTP boundary."""
from datetime import timezone

from sqlalchemy import case, select

from app.models import Department
from app.movement_models import Movement
from app.student_models import Institution, Student, StudentAcademicPlacement, utcnow

ACTIVE = ('EN_CAMINO', 'EN_ATENCION')


class MovementError(Exception):
    def __init__(self, code, message, status=409, **details):
        self.status = status
        self.detail = dict(code=code, message=message, **details)


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def active_for(session, student_id):
    return session.scalar(select(Movement).where(Movement.student_id == student_id, Movement.status.in_(ACTIVE)))


def active_summary(session, student_id):
    movement = active_for(session, student_id)
    if movement is None:
        return None
    return dict(status=movement.status, destination_name=session.scalar(
        select(Department.name).where(Department.id == movement.destination_department_id)))


def department_counts(session, department_id):
    statuses = session.scalars(select(Movement.status).where(
        Movement.destination_department_id == department_id, Movement.status.in_(ACTIVE))).all()
    return dict(en_camino=statuses.count('EN_CAMINO'), en_atencion=statuses.count('EN_ATENCION'))


def department_for_entry(session, identifier):
    department = session.get(Department, identifier)
    if department is None:
        raise MovementError('DEPARTAMENTO_NO_ENCONTRADO', 'Departamento no encontrado.', 404)
    if not department.active:
        raise MovementError('DEPARTAMENTO_INACTIVO', 'El departamento está inactivo.')
    if department.availability != 'DISPONIBLE':
        raise MovementError('DEPARTAMENTO_NO_DISPONIBLE', 'El departamento ya no está disponible. El estudiante no fue enviado.', destination_name=department.name)
    return department


def placement_for_entry(session, student_id):
    active = session.scalar(select(Student.active).where(Student.id == student_id))
    if active is None:
        raise MovementError('ESTUDIANTE_NO_ENCONTRADO', 'Estudiante no encontrado.', 404)
    if not active:
        raise MovementError('ESTUDIANTE_INACTIVO', 'El estudiante está inactivo.')
    period = session.scalar(select(Institution.active_academic_period_id).where(Institution.id == 1))
    placement = session.scalar(select(StudentAcademicPlacement.id).where(
        StudentAcademicPlacement.student_id == student_id,
        StudentAcademicPlacement.academic_period_id == period,
        StudentAcademicPlacement.recorded_to.is_(None))) if period else None
    if placement is None:
        raise MovementError('UBICACION_NO_DISPONIBLE', 'No hay una ubicación académica válida en el periodo activo.')
    return placement


def movement_result(session, movement):
    # Read only the operational name and placement fields, never contacts/documents.
    names = session.execute(select(Student.first_name, Student.middle_name, Student.last_name,
                                   Student.second_last_name).where(Student.id == movement.student_id)).one()
    placement = session.get(StudentAcademicPlacement, movement.academic_placement_id)
    return dict(id=movement.id, student_id=movement.student_id,
                academic_placement_id=movement.academic_placement_id,
                origin_department_id=movement.origin_department_id,
                destination_department_id=movement.destination_department_id,
                destination_name=session.scalar(select(Department.name).where(Department.id == movement.destination_department_id)),
                display_name=' '.join(n for n in names if n), course=placement.course, parallel=placement.parallel,
                status=movement.status, **{field: iso(getattr(movement, field)) for field in
                ('sent_at', 'arrived_at', 'finished_at', 'cancelled_at', 'created_at', 'updated_at')})


def create_movement(factory, student_id, destination_department_id, origin_department_id=None, direct=False):
    with factory() as session:
        session.connection(execution_options={'sqlite_write': True})
        placement = placement_for_entry(session, student_id)
        active = active_summary(session, student_id)
        if active:
            raise MovementError('ESTUDIANTE_ACTIVO', 'El estudiante ya tiene un movimiento activo. No se creó otro.', active_movement=active)
        department_for_entry(session, destination_department_id)
        if origin_department_id is not None:
            origin = session.get(Department, origin_department_id)
            if origin is None or not origin.active:
                raise MovementError('ORIGEN_INVALIDO', 'El departamento de origen no está activo.')
        now = utcnow()
        movement = Movement(student_id=student_id, academic_placement_id=placement,
            origin_department_id=None if direct else origin_department_id,
            destination_department_id=destination_department_id,
            status='EN_ATENCION' if direct else 'EN_CAMINO', sent_at=None if direct else now,
            arrived_at=now if direct else None, created_at=now, updated_at=now)
        session.add(movement)
        session.flush()
        result = movement_result(session, movement)
        try:
            session.commit()
        except Exception:
            session.rollback()
            raise
        return result, True


def transition(factory, movement_id, action):
    previous, target, timestamp = {
        'arrive': ('EN_CAMINO', 'EN_ATENCION', 'arrived_at'),
        'finish': ('EN_ATENCION', 'FINALIZADO', 'finished_at'),
        'cancel': ('EN_CAMINO', 'CANCELADO', 'cancelled_at'),
    }[action]
    with factory() as session:
        session.connection(execution_options={'sqlite_write': True})
        movement = session.get(Movement, movement_id)
        if movement is None:
            raise MovementError('MOVIMIENTO_NO_ENCONTRADO', 'Movimiento no encontrado.', 404)
        changed = movement.status != target
        if changed and movement.status != previous:
            raise MovementError('ESTADO_CAMBIADO', 'El estado del movimiento cambió. Consulta el panel actualizado.')
        if changed:
            # A backwards adjustment of the server clock must not create negative durations.
            now = max(utcnow(), movement.updated_at)
            movement.status = target
            setattr(movement, timestamp, now)
            movement.updated_at = now
            session.flush()
        result = movement_result(session, movement)
        try:
            session.commit()
        except Exception:
            session.rollback()
            raise
        return result, changed


def list_active(factory, department_id):
    with factory() as session:
        if session.get(Department, department_id) is None:
            raise MovementError('DEPARTAMENTO_NO_ENCONTRADO', 'Departamento no encontrado.', 404)
        rows = session.scalars(select(Movement).where(Movement.destination_department_id == department_id,
            Movement.status.in_(ACTIVE)).order_by(case((Movement.status == 'EN_ATENCION', 0), else_=1),
            case((Movement.status == 'EN_ATENCION', Movement.arrived_at), else_=Movement.sent_at), Movement.id))
        return dict(items=[movement_result(session, row) for row in rows], server_now=iso(utcnow()))


def student_status(factory, student_id):
    with factory() as session:
        placement_for_entry(session, student_id)
        return dict(active_movement=active_summary(session, student_id), server_now=iso(utcnow()))
