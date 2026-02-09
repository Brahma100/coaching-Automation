"""rule config and pending actions

Revision ID: 20260209_0003
Revises: 20260209_0002
Create Date: 2026-02-09 00:03:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260209_0003'
down_revision = '20260209_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'rule_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.Integer(), nullable=True),
        sa.Column('absence_streak_threshold', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('notify_parent_on_absence', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('notify_parent_on_fee_due', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('reminder_grace_period_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_rule_configs_id', 'rule_configs', ['id'])
    op.create_index('ix_rule_configs_batch_id', 'rule_configs', ['batch_id'])

    op.create_table(
        'pending_actions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('type', sa.String(length=30), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=True),
        sa.Column('related_session_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('note', sa.Text(), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_pending_actions_id', 'pending_actions', ['id'])
    op.create_index('ix_pending_actions_type', 'pending_actions', ['type'])
    op.create_index('ix_pending_actions_student_id', 'pending_actions', ['student_id'])
    op.create_index('ix_pending_actions_related_session_id', 'pending_actions', ['related_session_id'])
    op.create_index('ix_pending_actions_status', 'pending_actions', ['status'])


def downgrade() -> None:
    op.drop_index('ix_pending_actions_status', table_name='pending_actions')
    op.drop_index('ix_pending_actions_related_session_id', table_name='pending_actions')
    op.drop_index('ix_pending_actions_student_id', table_name='pending_actions')
    op.drop_index('ix_pending_actions_type', table_name='pending_actions')
    op.drop_index('ix_pending_actions_id', table_name='pending_actions')
    op.drop_table('pending_actions')

    op.drop_index('ix_rule_configs_batch_id', table_name='rule_configs')
    op.drop_index('ix_rule_configs_id', table_name='rule_configs')
    op.drop_table('rule_configs')
