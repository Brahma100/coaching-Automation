"""notification dedup hardening

Revision ID: 20260210_0014
Revises: 20260210_0013
Create Date: 2026-02-10 00:14:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260210_0014'
down_revision = '20260210_0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    comm_cols = {col['name'] for col in inspector.get_columns('communication_logs')}

    if 'session_id' not in comm_cols:
        op.add_column('communication_logs', sa.Column('session_id', sa.Integer(), nullable=True))
        op.create_index('ix_communication_logs_session_id', 'communication_logs', ['session_id'])
    if 'notification_type' not in comm_cols:
        op.add_column(
            'communication_logs',
            sa.Column('notification_type', sa.String(length=40), nullable=False, server_default=''),
        )
        op.create_index('ix_communication_logs_notification_type', 'communication_logs', ['notification_type'])

    op.execute(
        """
        UPDATE communication_logs
        SET session_id = reference_id
        WHERE session_id IS NULL AND reference_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE communication_logs
        SET notification_type = event_type
        WHERE notification_type = '' AND event_type IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE communication_logs
        SET notification_type = 'unknown'
        WHERE notification_type = ''
        """
    )

    op.execute(
        """
        DELETE FROM communication_logs
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM communication_logs
            WHERE teacher_id IS NOT NULL
              AND session_id IS NOT NULL
              AND notification_type IS NOT NULL
            GROUP BY teacher_id, session_id, notification_type
        )
        AND teacher_id IS NOT NULL
        AND session_id IS NOT NULL
        AND notification_type IS NOT NULL
        """
    )

    indexes = {idx['name'] for idx in inspector.get_indexes('communication_logs')}
    if 'uq_comm_logs_teacher_session_type' not in indexes:
        op.create_index(
            'uq_comm_logs_teacher_session_type',
            'communication_logs',
            ['teacher_id', 'session_id', 'notification_type'],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index('uq_comm_logs_teacher_session_type', table_name='communication_logs')
    op.drop_index('ix_communication_logs_notification_type', table_name='communication_logs')
    op.drop_column('communication_logs', 'notification_type')
    op.drop_index('ix_communication_logs_session_id', table_name='communication_logs')
    op.drop_column('communication_logs', 'session_id')
