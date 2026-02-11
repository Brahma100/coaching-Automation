"""teacher notification preferences and logs

Revision ID: 20260210_0012
Revises: 20260210_0011
Create Date: 2026-02-10 00:12:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260210_0012'
down_revision = '20260209_0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    auth_cols = {col['name'] for col in inspector.get_columns('auth_users')}
    if 'notification_delete_minutes' not in auth_cols:
        op.add_column(
            'auth_users',
            sa.Column('notification_delete_minutes', sa.Integer(), nullable=False, server_default='15'),
        )

    comm_cols = {col['name'] for col in inspector.get_columns('communication_logs')}
    if 'teacher_id' not in comm_cols:
        op.add_column('communication_logs', sa.Column('teacher_id', sa.Integer(), nullable=True))
        op.create_index('ix_communication_logs_teacher_id', 'communication_logs', ['teacher_id'])
    if 'telegram_message_id' not in comm_cols:
        op.add_column('communication_logs', sa.Column('telegram_message_id', sa.Integer(), nullable=True))
    if 'delete_at' not in comm_cols:
        op.add_column('communication_logs', sa.Column('delete_at', sa.DateTime(), nullable=True))
        op.create_index('ix_communication_logs_delete_at', 'communication_logs', ['delete_at'])
    if 'event_type' not in comm_cols:
        op.add_column('communication_logs', sa.Column('event_type', sa.String(length=40), nullable=True))
        op.create_index('ix_communication_logs_event_type', 'communication_logs', ['event_type'])
    if 'reference_id' not in comm_cols:
        op.add_column('communication_logs', sa.Column('reference_id', sa.Integer(), nullable=True))
        op.create_index('ix_communication_logs_reference_id', 'communication_logs', ['reference_id'])


def downgrade() -> None:
    op.drop_index('ix_communication_logs_reference_id', table_name='communication_logs')
    op.drop_column('communication_logs', 'reference_id')
    op.drop_index('ix_communication_logs_event_type', table_name='communication_logs')
    op.drop_column('communication_logs', 'event_type')
    op.drop_index('ix_communication_logs_delete_at', table_name='communication_logs')
    op.drop_column('communication_logs', 'delete_at')
    op.drop_column('communication_logs', 'telegram_message_id')
    op.drop_index('ix_communication_logs_teacher_id', table_name='communication_logs')
    op.drop_column('communication_logs', 'teacher_id')

    op.drop_column('auth_users', 'notification_delete_minutes')
