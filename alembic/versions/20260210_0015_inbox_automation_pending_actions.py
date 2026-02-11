"""inbox automation pending actions

Revision ID: 20260210_0015
Revises: 20260210_0014
Create Date: 2026-02-10 00:15:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260210_0015'
down_revision = '20260210_0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {col['name'] for col in inspector.get_columns('pending_actions')}

    if 'action_type' not in cols:
        op.add_column('pending_actions', sa.Column('action_type', sa.String(length=40), nullable=False, server_default=''))
        op.create_index('ix_pending_actions_action_type', 'pending_actions', ['action_type'])
    if 'teacher_id' not in cols:
        op.add_column('pending_actions', sa.Column('teacher_id', sa.Integer(), nullable=True))
        op.create_index('ix_pending_actions_teacher_id', 'pending_actions', ['teacher_id'])
    if 'session_id' not in cols:
        op.add_column('pending_actions', sa.Column('session_id', sa.Integer(), nullable=True))
        op.create_index('ix_pending_actions_session_id', 'pending_actions', ['session_id'])
    if 'due_at' not in cols:
        op.add_column('pending_actions', sa.Column('due_at', sa.DateTime(), nullable=True))
        op.create_index('ix_pending_actions_due_at', 'pending_actions', ['due_at'])
    if 'resolved_at' not in cols:
        op.add_column('pending_actions', sa.Column('resolved_at', sa.DateTime(), nullable=True))
    if 'resolution_note' not in cols:
        op.add_column('pending_actions', sa.Column('resolution_note', sa.Text(), nullable=False, server_default=''))
    if 'escalation_sent_at' not in cols:
        op.add_column('pending_actions', sa.Column('escalation_sent_at', sa.DateTime(), nullable=True))

    op.execute(
        """
        UPDATE pending_actions
        SET action_type = type
        WHERE action_type = '' AND type IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE pending_actions
        SET session_id = related_session_id
        WHERE session_id IS NULL AND related_session_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE pending_actions
        SET teacher_id = (
            SELECT teacher_id FROM class_sessions
            WHERE class_sessions.id = pending_actions.related_session_id
        )
        WHERE teacher_id IS NULL AND related_session_id IS NOT NULL
        """
    )

    indexes = {idx['name'] for idx in inspector.get_indexes('pending_actions')}
    if 'uq_pending_actions_teacher_session_type_student' not in indexes:
        op.create_index(
            'uq_pending_actions_teacher_session_type_student',
            'pending_actions',
            ['teacher_id', 'session_id', 'action_type', 'student_id'],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index('uq_pending_actions_teacher_session_type_student', table_name='pending_actions')
    op.drop_index('ix_pending_actions_due_at', table_name='pending_actions')
    op.drop_column('pending_actions', 'due_at')
    op.drop_column('pending_actions', 'escalation_sent_at')
    op.drop_column('pending_actions', 'resolved_at')
    op.drop_column('pending_actions', 'resolution_note')
    op.drop_index('ix_pending_actions_session_id', table_name='pending_actions')
    op.drop_column('pending_actions', 'session_id')
    op.drop_index('ix_pending_actions_teacher_id', table_name='pending_actions')
    op.drop_column('pending_actions', 'teacher_id')
    op.drop_index('ix_pending_actions_action_type', table_name='pending_actions')
    op.drop_column('pending_actions', 'action_type')
