"""Modelo persistente de departamentos."""

from sqlalchemy import Boolean, CheckConstraint, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.database import metadata


class Base(DeclarativeBase):
    metadata = metadata


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (
        CheckConstraint('"group" IN (\'INSPECCION\', \'DECE\', \'SALUD\')', name="ck_departments_group"),
        CheckConstraint("availability IN ('DISPONIBLE', 'NO_DISPONIBLE')", name="ck_departments_availability"),
        CheckConstraint("active IN (0, 1)", name="ck_departments_active"),
        CheckConstraint("length(name) BETWEEN 1 AND 120 AND name = trim(name)", name="ck_departments_name"),
        UniqueConstraint("group", "name", name="uq_departments_group_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    group: Mapped[str] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("1"), default=True)
    availability: Mapped[str] = mapped_column(String(13), server_default="DISPONIBLE", default="DISPONIBLE")
