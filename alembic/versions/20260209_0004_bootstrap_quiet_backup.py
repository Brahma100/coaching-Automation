"""bootstrap safety, quiet hours, backup logs

Revision ID: 20260209_0004
Revises: 20260209_0003
Create Date: 2026-02-09 00:04:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260209_0004'
down_revision = '20260209_0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('rule_configs', sa.Column('quiet_hours_start', sa.String(length=5), nullable=False, server_default='22:00'))
    op.add_column('rule_configs', sa.Column('quiet_hours_end', sa.String(length=5), nullable=False, server_default='06:00'))

    op.create_table(
        'staff_users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_staff_users_id', 'staff_users', ['id'])
    op.create_index('ix_staff_users_username', 'staff_users', ['username'], unique=True)
    op.create_index('ix_staff_users_role', 'staff_users', ['role'])

    op.create_table(
        'backup_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='failed'),
        sa.Column('message', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_backup_logs_id', 'backup_logs', ['id'])
    op.create_index('ix_backup_logs_status', 'backup_logs', ['status'])


def downgrade() -> None:
    op.drop_index('ix_backup_logs_status', table_name='backup_logs')
    op.drop_index('ix_backup_logs_id', table_name='backup_logs')
    op.drop_table('backup_logs')

    op.drop_index('ix_staff_users_role', table_name='staff_users')
    op.drop_index('ix_staff_users_username', table_name='staff_users')
    op.drop_index('ix_staff_users_id', table_name='staff_users')
    op.drop_table('staff_users')

    op.drop_column('rule_configs', 'quiet_hours_end')
    op.drop_column('rule_configs', 'quiet_hours_start')
