"""Add safe application receipt and field provenance for imports.

Revision ID: 0003_import_apply
Revises: 0002_import_preview
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_import_apply"
down_revision: Union[str, Sequence[str], None] = "0002_import_preview"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite cannot alter a CHECK constraint. Batch recreation preserves all existing
    # preview rows and referencing foreign keys while adding the one new status.
    with op.batch_alter_table("import_batches", recreate="always") as batch:
        batch.drop_constraint("ck_import_status", type_="check")
        batch.add_column(sa.Column("application_contract_version", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("applied_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("applied_result", sa.JSON(none_as_null=True), nullable=True))
        batch.create_check_constraint("ck_import_status", "status IN ('PREVIEW','EXPIRED','APPLIED')")
        batch.create_check_constraint(
            "ck_import_application_state",
            "(status = 'APPLIED' AND applied_at IS NOT NULL AND applied_result IS NOT NULL) "
            "OR (status != 'APPLIED' AND applied_at IS NULL AND applied_result IS NULL)",
        )
    with op.batch_alter_table("students") as batch:
        batch.add_column(sa.Column("manual_protected_fields", sa.JSON(none_as_null=True), nullable=True))
    with op.batch_alter_table("student_contacts") as batch:
        batch.add_column(sa.Column("manual_protected_fields", sa.JSON(none_as_null=True), nullable=True))
    with op.batch_alter_table("student_academic_placements") as batch:
        batch.add_column(sa.Column("source_baseline", sa.JSON(none_as_null=True), nullable=True))
        batch.add_column(sa.Column("manual_protected_fields", sa.JSON(none_as_null=True), nullable=True))


def downgrade() -> None:
    # A receipt cannot be represented by the older schema without losing its
    # idempotency guarantee. Refuse this downgrade rather than make it re-applicable.
    if op.get_bind().execute(sa.text("SELECT count(*) FROM import_batches WHERE status='APPLIED'")).scalar():
        raise RuntimeError("No se puede revertir 0003 mientras existan importaciones aplicadas.")
    with op.batch_alter_table("student_academic_placements") as batch:
        batch.drop_column("manual_protected_fields")
        batch.drop_column("source_baseline")
    with op.batch_alter_table("student_contacts") as batch:
        batch.drop_column("manual_protected_fields")
    with op.batch_alter_table("students") as batch:
        batch.drop_column("manual_protected_fields")
    with op.batch_alter_table("import_batches", recreate="always") as batch:
        batch.drop_constraint("ck_import_application_state", type_="check")
        batch.drop_constraint("ck_import_status", type_="check")
        batch.drop_column("applied_result")
        batch.drop_column("applied_at")
        batch.drop_column("application_contract_version")
        batch.create_check_constraint("ck_import_status", "status IN ('PREVIEW','EXPIRED')")
