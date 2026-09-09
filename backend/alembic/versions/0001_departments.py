"""Create the department catalogue and its eight initial entries."""

from alembic import op
import sqlalchemy as sa

revision = "0001_departments"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    departments = op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("group", sa.String(10), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("availability", sa.String(13), nullable=False, server_default="DISPONIBLE"),
        sa.CheckConstraint('"group" IN (\'INSPECCION\', \'DECE\', \'SALUD\')', name="ck_departments_group"),
        sa.CheckConstraint("availability IN ('DISPONIBLE', 'NO_DISPONIBLE')", name="ck_departments_availability"),
        sa.CheckConstraint("active IN (0, 1)", name="ck_departments_active"),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 120 AND name = trim(name)", name="ck_departments_name"),
        sa.UniqueConstraint("group", "name", name="uq_departments_group_name"),
    )
    op.bulk_insert(departments, [
        {"name": name, "group": group}
        for group, name in [
            ("INSPECCION", "Inspección General"),
            ("INSPECCION", "Inspección Primaria"),
            ("INSPECCION", "Inspección Bachillerato"),
            ("DECE", "DECE Primaria"),
            ("DECE", "DECE Secundaria/Bachillerato"),
            ("DECE", "Psicopedagogía"),
            ("SALUD", "Departamento Médico"),
            ("SALUD", "Departamento Odontológico"),
        ]
    ])


def downgrade() -> None:
    op.drop_table("departments")
