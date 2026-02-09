"""batch schedules and multi-batch student mapping

Revision ID: 20260209_0008
Revises: 20260209_0007
Create Date: 2026-02-09 00:08:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260209_0008'
down_revision = '20260209_0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    batch_columns = {col['name'] for col in inspector.get_columns('batches')}
    if 'subject' not in batch_columns:
        op.add_column('batches', sa.Column('subject', sa.String(length=120), nullable=False, server_default='General'))
    if 'academic_level' not in batch_columns:
        op.add_column('batches', sa.Column('academic_level', sa.String(length=20), nullable=False, server_default=''))
    if 'active' not in batch_columns:
        op.add_column('batches', sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()))
    if 'created_at' not in batch_columns:
        op.add_column(
            'batches',
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default='1970-01-01 00:00:00'),
        )
        op.execute("UPDATE batches SET created_at = CURRENT_TIMESTAMP WHERE created_at = '1970-01-01 00:00:00'")

    batch_indexes = {idx['name'] for idx in inspector.get_indexes('batches')}
    if 'ix_batches_subject' not in batch_indexes:
        op.create_index('ix_batches_subject', 'batches', ['subject'])
    if 'ix_batches_active' not in batch_indexes:
        op.create_index('ix_batches_active', 'batches', ['active'])

    op.execute("UPDATE batches SET subject = COALESCE(NULLIF(name, ''), 'General')")

    class_session_columns = {col['name'] for col in inspector.get_columns('class_sessions')}
    if 'duration_minutes' not in class_session_columns:
        op.add_column('class_sessions', sa.Column('duration_minutes', sa.Integer(), nullable=False, server_default='60'))

    tables = set(inspector.get_table_names())
    if 'batch_schedules' not in tables:
        op.create_table(
            'batch_schedules',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('batch_id', sa.Integer(), sa.ForeignKey('batches.id'), nullable=False),
            sa.Column('weekday', sa.Integer(), nullable=False),
            sa.Column('start_time', sa.String(length=5), nullable=False),
            sa.Column('duration_minutes', sa.Integer(), nullable=False, server_default='60'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default='1970-01-01 00:00:00'),
        )
        op.execute("UPDATE batch_schedules SET created_at = CURRENT_TIMESTAMP WHERE created_at = '1970-01-01 00:00:00'")

    if 'student_batch_map' not in tables:
        op.create_table(
            'student_batch_map',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
            sa.Column('batch_id', sa.Integer(), sa.ForeignKey('batches.id'), nullable=False),
            sa.Column('joined_at', sa.DateTime(), nullable=False, server_default='1970-01-01 00:00:00'),
            sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        op.execute("UPDATE student_batch_map SET joined_at = CURRENT_TIMESTAMP WHERE joined_at = '1970-01-01 00:00:00'")

    if 'batch_schedules' in inspector.get_table_names():
        idx_names = {idx['name'] for idx in inspector.get_indexes('batch_schedules')}
        if 'ix_batch_schedules_id' not in idx_names:
            op.create_index('ix_batch_schedules_id', 'batch_schedules', ['id'])
        if 'ix_batch_schedules_batch_id' not in idx_names:
            op.create_index('ix_batch_schedules_batch_id', 'batch_schedules', ['batch_id'])
        if 'ix_batch_schedules_weekday' not in idx_names:
            op.create_index('ix_batch_schedules_weekday', 'batch_schedules', ['weekday'])

    if 'student_batch_map' in inspector.get_table_names():
        idx_names = {idx['name'] for idx in inspector.get_indexes('student_batch_map')}
        if 'ix_student_batch_map_id' not in idx_names:
            op.create_index('ix_student_batch_map_id', 'student_batch_map', ['id'])
        if 'ix_student_batch_map_student_id' not in idx_names:
            op.create_index('ix_student_batch_map_student_id', 'student_batch_map', ['student_id'])
        if 'ix_student_batch_map_batch_id' not in idx_names:
            op.create_index('ix_student_batch_map_batch_id', 'student_batch_map', ['batch_id'])
        if 'ix_student_batch_map_active' not in idx_names:
            op.create_index('ix_student_batch_map_active', 'student_batch_map', ['active'])
        if 'uq_student_batch_map_active_pair' not in idx_names:
            op.create_index(
                'uq_student_batch_map_active_pair',
                'student_batch_map',
                ['student_id', 'batch_id'],
                unique=True,
                sqlite_where=sa.text('active = 1'),
            )

        # Seed mapping table from existing primary batch assignments.
        op.execute(
            """
            INSERT INTO student_batch_map (student_id, batch_id, joined_at, active)
            SELECT s.id, s.batch_id, CURRENT_TIMESTAMP, 1
            FROM students s
            LEFT JOIN student_batch_map m
              ON m.student_id = s.id AND m.batch_id = s.batch_id AND m.active = 1
            WHERE m.id IS NULL
            """
        )


def downgrade() -> None:
    op.drop_index('uq_student_batch_map_active_pair', table_name='student_batch_map')
    op.drop_index('ix_student_batch_map_active', table_name='student_batch_map')
    op.drop_index('ix_student_batch_map_batch_id', table_name='student_batch_map')
    op.drop_index('ix_student_batch_map_student_id', table_name='student_batch_map')
    op.drop_index('ix_student_batch_map_id', table_name='student_batch_map')
    op.drop_table('student_batch_map')

    op.drop_index('ix_batch_schedules_weekday', table_name='batch_schedules')
    op.drop_index('ix_batch_schedules_batch_id', table_name='batch_schedules')
    op.drop_index('ix_batch_schedules_id', table_name='batch_schedules')
    op.drop_table('batch_schedules')

    op.drop_column('class_sessions', 'duration_minutes')

    op.drop_index('ix_batches_active', table_name='batches')
    op.drop_index('ix_batches_subject', table_name='batches')
    op.drop_column('batches', 'created_at')
    op.drop_column('batches', 'active')
    op.drop_column('batches', 'academic_level')
    op.drop_column('batches', 'subject')
