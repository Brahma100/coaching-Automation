"""Performance indexes for frequent filters

Revision ID: 20260211_0018
Revises: 20260210_0017
Create Date: 2026-02-11 00:18:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260211_0018'
down_revision = '20260210_0017'
branch_labels = None
depends_on = None


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    return any(idx.get('name') == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'students' in existing_tables and not _index_exists(inspector, 'students', 'ix_students_batch_id'):
        op.create_index('ix_students_batch_id', 'students', ['batch_id'])

    if 'attendance_records' in existing_tables and not _index_exists(inspector, 'attendance_records', 'ix_attendance_records_student_date'):
        op.create_index(
            'ix_attendance_records_student_date',
            'attendance_records',
            ['student_id', 'attendance_date'],
        )

    if 'class_sessions' in existing_tables and not _index_exists(inspector, 'class_sessions', 'ix_class_sessions_batch_scheduled_start'):
        op.create_index(
            'ix_class_sessions_batch_scheduled_start',
            'class_sessions',
            ['batch_id', 'scheduled_start'],
        )

    if 'pending_actions' in existing_tables and not _index_exists(inspector, 'pending_actions', 'ix_pending_actions_status_teacher_due'):
        op.create_index(
            'ix_pending_actions_status_teacher_due',
            'pending_actions',
            ['status', 'teacher_id', 'due_at'],
        )

    if 'pending_actions' in existing_tables and not _index_exists(inspector, 'pending_actions', 'ix_pending_actions_teacher_status'):
        op.create_index(
            'ix_pending_actions_teacher_status',
            'pending_actions',
            ['teacher_id', 'status'],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'pending_actions' in existing_tables and _index_exists(inspector, 'pending_actions', 'ix_pending_actions_teacher_status'):
        op.drop_index('ix_pending_actions_teacher_status', table_name='pending_actions')

    if 'pending_actions' in existing_tables and _index_exists(inspector, 'pending_actions', 'ix_pending_actions_status_teacher_due'):
        op.drop_index('ix_pending_actions_status_teacher_due', table_name='pending_actions')

    if 'class_sessions' in existing_tables and _index_exists(inspector, 'class_sessions', 'ix_class_sessions_batch_scheduled_start'):
        op.drop_index('ix_class_sessions_batch_scheduled_start', table_name='class_sessions')

    if 'attendance_records' in existing_tables and _index_exists(inspector, 'attendance_records', 'ix_attendance_records_student_date'):
        op.drop_index('ix_attendance_records_student_date', table_name='attendance_records')

    if 'students' in existing_tables and _index_exists(inspector, 'students', 'ix_students_batch_id'):
        op.drop_index('ix_students_batch_id', table_name='students')
