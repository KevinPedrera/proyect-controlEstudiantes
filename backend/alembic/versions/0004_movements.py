"""Add movement history without changing existing records.

Revision ID: 0004_movements
Revises: 0003_import_apply
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_movements'
down_revision = '0003_import_apply'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'movements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('academic_placement_id', sa.Integer(), sa.ForeignKey('student_academic_placements.id'), nullable=False),
        sa.Column('origin_department_id', sa.Integer(), sa.ForeignKey('departments.id')),
        sa.Column('destination_department_id', sa.Integer(), sa.ForeignKey('departments.id'), nullable=False),
        sa.Column('status', sa.String(12), nullable=False),
        sa.Column('sent_at', sa.DateTime()), sa.Column('arrived_at', sa.DateTime()),
        sa.Column('finished_at', sa.DateTime()), sa.Column('cancelled_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('EN_CAMINO','EN_ATENCION','FINALIZADO','CANCELADO')", name='ck_movement_status'),
        sa.CheckConstraint("(status = 'EN_CAMINO' AND sent_at IS NOT NULL AND arrived_at IS NULL AND finished_at IS NULL AND cancelled_at IS NULL) OR (status = 'EN_ATENCION' AND arrived_at IS NOT NULL AND finished_at IS NULL AND cancelled_at IS NULL) OR (status = 'FINALIZADO' AND arrived_at IS NOT NULL AND finished_at IS NOT NULL AND cancelled_at IS NULL) OR (status = 'CANCELADO' AND sent_at IS NOT NULL AND arrived_at IS NULL AND finished_at IS NULL AND cancelled_at IS NOT NULL)", name='ck_movement_timestamps'),
        sa.CheckConstraint("(sent_at IS NULL OR sent_at >= created_at) AND (arrived_at IS NULL OR arrived_at >= coalesce(sent_at, created_at)) AND (finished_at IS NULL OR finished_at >= arrived_at) AND (cancelled_at IS NULL OR cancelled_at >= sent_at) AND updated_at >= created_at", name='ck_movement_chronology'),
        sa.CheckConstraint('sent_at IS NOT NULL OR origin_department_id IS NULL', name='ck_movement_direct_origin'),
    )
    op.create_index('uq_movement_active_student', 'movements', ['student_id'], unique=True, sqlite_where=sa.text("status IN ('EN_CAMINO','EN_ATENCION')"))
    op.create_index('ix_movement_destination_active', 'movements', ['destination_department_id', 'status'])


def downgrade():
    op.drop_table('movements')
