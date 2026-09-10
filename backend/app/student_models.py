"""Esquema de previews 3A y aplicación 3B. Solo confirmar escribe datos operativos."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


def utcnow() -> datetime:
    """SQLite guarda UTC sin zona; la API añade el sufijo Z."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint("scope IN ('PADRON_COMPLETO','SUBCONJUNTO')", name="ck_import_scope"),
        CheckConstraint("status IN ('PREVIEW','EXPIRED','APPLIED')", name="ck_import_status"),
        CheckConstraint("(status = 'APPLIED' AND applied_at IS NOT NULL AND applied_result IS NOT NULL) OR (status != 'APPLIED' AND applied_at IS NULL AND applied_result IS NULL)", name="ck_import_application_state"),
        CheckConstraint("expires_at > created_at", name="ck_import_expiry"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile: Mapped[str] = mapped_column(String(64))
    file_hash: Mapped[str] = mapped_column(String(64))
    scope: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(12), default="PREVIEW")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    # Entire snapshot is purged on expiry, including absence and candidate data.
    proposal: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    # This is deliberately distinct from the parser profile: old drafts remain readable
    # but cannot be applied after the application rules change.
    application_contract_version: Mapped[str | None] = mapped_column(String(32))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)
    # A permanent, deliberately non-personal receipt. Preview payload remains temporary.
    applied_result: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))


class AcademicPeriod(Base):
    __tablename__ = "academic_periods"
    __table_args__ = (CheckConstraint("length(trim(label)) > 0 AND length(period_key) > 0", name="ck_period_label"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(80))
    period_key: Mapped[str] = mapped_column(String(80), unique=True)


class Institution(Base):
    __tablename__ = "institution"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_institution_singleton"),
        CheckConstraint("length(trim(name)) > 0", name="ck_institution_name"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(240))
    active_academic_period_id: Mapped[int | None] = mapped_column(ForeignKey("academic_periods.id"))


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint("length(trim(first_name)) > 0 AND length(trim(last_name)) > 0", name="ck_student_names"),
        CheckConstraint("active IN (0,1)", name="ck_student_active"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(160))
    middle_name: Mapped[str | None] = mapped_column(String(160))
    last_name: Mapped[str] = mapped_column(String(160))
    second_last_name: Mapped[str | None] = mapped_column(String(160))
    document: Mapped[str | None] = mapped_column(String(80), index=True)
    document_type: Mapped[str | None] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    source_batch_id: Mapped[str | None] = mapped_column(ForeignKey("import_batches.id"))
    # Future accepted BASE is independent of temporary preview retention.
    source_baseline: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    manual_protected_fields: Mapped[list | None] = mapped_column(JSON(none_as_null=True))


class StudentAcademicPlacement(Base):
    __tablename__ = "student_academic_placements"
    __table_args__ = (
        CheckConstraint("length(trim(course)) > 0 AND length(trim(parallel)) > 0", name="ck_placement_fields"),
        CheckConstraint("recorded_to IS NULL OR recorded_to >= recorded_from", name="ck_placement_dates"),
        Index("uq_placement_open", "student_id", "academic_period_id", unique=True, sqlite_where=text("recorded_to IS NULL")),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    academic_period_id: Mapped[int] = mapped_column(ForeignKey("academic_periods.id"))
    course: Mapped[str] = mapped_column(String(160))
    parallel: Mapped[str] = mapped_column(String(40))
    recorded_from: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    recorded_to: Mapped[datetime | None] = mapped_column(DateTime)
    source_batch_id: Mapped[str | None] = mapped_column(ForeignKey("import_batches.id"))
    source_baseline: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    manual_protected_fields: Mapped[list | None] = mapped_column(JSON(none_as_null=True))


class StudentContact(Base):
    __tablename__ = "student_contacts"
    __table_args__ = (
        CheckConstraint("type IN ('REPRESENTANTE_LEGAL','PADRE','MADRE','EMERGENCIA')", name="ck_contact_type"),
        CheckConstraint("active IN (0,1)", name="ck_contact_active"),
        Index("uq_contact_single_role", "student_id", "type", unique=True, sqlite_where=text("active = 1 AND type != 'EMERGENCIA'")),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    type: Mapped[str] = mapped_column(String(24))
    relationship: Mapped[str | None] = mapped_column(String(80))
    first_name: Mapped[str | None] = mapped_column(String(160))
    middle_name: Mapped[str | None] = mapped_column(String(160))
    last_name: Mapped[str | None] = mapped_column(String(160))
    second_last_name: Mapped[str | None] = mapped_column(String(160))
    home_phone: Mapped[str | None] = mapped_column(String(80))
    mobile_phone: Mapped[str | None] = mapped_column(String(80))
    work_phone: Mapped[str | None] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    source_batch_id: Mapped[str | None] = mapped_column(ForeignKey("import_batches.id"))
    source_baseline: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    manual_protected_fields: Mapped[list | None] = mapped_column(JSON(none_as_null=True))


class ImportRow(Base):
    __tablename__ = "import_rows"
    __table_args__ = (
        UniqueConstraint("batch_id", "row_number", name="uq_import_row"),
        CheckConstraint("category IN ('NUEVO','SIN_CAMBIOS','ACTUALIZACION','REQUIERE_REVISION')", name="ck_import_category"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(24))
    payload: Mapped[dict] = mapped_column(JSON)
