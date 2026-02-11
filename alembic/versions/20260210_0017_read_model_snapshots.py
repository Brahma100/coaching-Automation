"""CQRS-lite read model snapshots

Revision ID: 20260210_0017
Revises: 20260210_0016
Create Date: 2026-02-10 00:17:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260210_0017'
down_revision = '20260210_0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'teacher_today_snapshot' not in existing_tables:
        op.create_table(
            'teacher_today_snapshot',
            sa.Column('teacher_id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('date', sa.Date(), primary_key=True, nullable=False),
            sa.Column('data_json', sa.Text(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('ix_teacher_today_snapshot_updated_at', 'teacher_today_snapshot', ['updated_at'])

    if 'admin_ops_snapshot' not in existing_tables:
        op.create_table(
            'admin_ops_snapshot',
            sa.Column('date', sa.Date(), primary_key=True, nullable=False),
            sa.Column('data_json', sa.Text(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('ix_admin_ops_snapshot_updated_at', 'admin_ops_snapshot', ['updated_at'])

    if 'student_dashboard_snapshot' not in existing_tables:
        op.create_table(
            'student_dashboard_snapshot',
            sa.Column('student_id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('date', sa.Date(), primary_key=True, nullable=False),
            sa.Column('data_json', sa.Text(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )
        op.create_index('ix_student_dashboard_snapshot_updated_at', 'student_dashboard_snapshot', ['updated_at'])


def downgrade() -> None:
    op.drop_index('ix_student_dashboard_snapshot_updated_at', table_name='student_dashboard_snapshot')
    op.drop_table('student_dashboard_snapshot')
    op.drop_index('ix_admin_ops_snapshot_updated_at', table_name='admin_ops_snapshot')
    op.drop_table('admin_ops_snapshot')
    op.drop_index('ix_teacher_today_snapshot_updated_at', table_name='teacher_today_snapshot')
    op.drop_table('teacher_today_snapshot')

