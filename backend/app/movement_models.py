"""Persistent movement history; no operational counters or personal contact data."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Movement(Base):
    __tablename__ = 'movements'
    __table_args__ = (
        CheckConstraint("status IN ('EN_CAMINO','EN_ATENCION','FINALIZADO','CANCELADO')", name='ck_movement_status'),
        CheckConstraint("(status = 'EN_CAMINO' AND sent_at IS NOT NULL AND arrived_at IS NULL AND finished_at IS NULL AND cancelled_at IS NULL) OR (status = 'EN_ATENCION' AND arrived_at IS NOT NULL AND finished_at IS NULL AND cancelled_at IS NULL) OR (status = 'FINALIZADO' AND arrived_at IS NOT NULL AND finished_at IS NOT NULL AND cancelled_at IS NULL) OR (status = 'CANCELADO' AND sent_at IS NOT NULL AND arrived_at IS NULL AND finished_at IS NULL AND cancelled_at IS NOT NULL)", name='ck_movement_timestamps'),
        CheckConstraint("(sent_at IS NULL OR sent_at >= created_at) AND (arrived_at IS NULL OR arrived_at >= coalesce(sent_at, created_at)) AND (finished_at IS NULL OR finished_at >= arrived_at) AND (cancelled_at IS NULL OR cancelled_at >= sent_at) AND updated_at >= created_at", name='ck_movement_chronology'),
        CheckConstraint('sent_at IS NOT NULL OR origin_department_id IS NULL', name='ck_movement_direct_origin'),
        Index('uq_movement_active_student', 'student_id', unique=True, sqlite_where=text("status IN ('EN_CAMINO','EN_ATENCION')")),
        Index('ix_movement_destination_active', 'destination_department_id', 'status'),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'))
    academic_placement_id: Mapped[int] = mapped_column(ForeignKey('student_academic_placements.id'))
    origin_department_id: Mapped[int | None] = mapped_column(ForeignKey('departments.id'))
    destination_department_id: Mapped[int] = mapped_column(ForeignKey('departments.id'))
    status: Mapped[str] = mapped_column(String(12))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
