"""Teacher calendar overrides and additional indexes

Revision ID: 20260211_0019
Revises: 20260211_0018
Create Date: 2026-02-11 01:19:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260211_0019'
down_revision = '20260211_0018'
branch_labels = None
depends_on = None


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    return any(idx.get('name') == index_name for idx in inspector.get_indexes(table_name))


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, 'calendar_overrides'):
        op.create_table(
            'calendar_overrides',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('batch_id', sa.Integer(), nullable=False),
            sa.Column('override_date', sa.Date(), nullable=False),
            sa.Column('new_start_time', sa.String(length=5), nullable=True),
            sa.Column('new_duration_minutes', sa.Integer(), nullable=True),
            sa.Column('cancelled', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('reason', sa.Text(), nullable=False, server_default=''),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.ForeignKeyConstraint(['batch_id'], ['batches.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    inspector = sa.inspect(bind)

    if _table_exists(inspector, 'calendar_overrides') and not _index_exists(inspector, 'calendar_overrides', 'ix_calendar_overrides_batch_date'):
        op.create_index('ix_calendar_overrides_batch_date', 'calendar_overrides', ['batch_id', 'override_date'])

    if _table_exists(inspector, 'batch_schedules') and not _index_exists(inspector, 'batch_schedules', 'ix_batch_schedules_weekday_start_time'):
        op.create_index('ix_batch_schedules_weekday_start_time', 'batch_schedules', ['weekday', 'start_time'])

    if _table_exists(inspector, 'student_batch_map') and not _index_exists(inspector, 'student_batch_map', 'ix_student_batch_map_batch_active'):
        op.create_index('ix_student_batch_map_batch_active', 'student_batch_map', ['batch_id', 'active'])

    if _table_exists(inspector, 'fee_records') and not _index_exists(inspector, 'fee_records', 'ix_fee_records_student_due_paid'):
        op.create_index('ix_fee_records_student_due_paid', 'fee_records', ['student_id', 'due_date', 'is_paid'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, 'fee_records') and _index_exists(inspector, 'fee_records', 'ix_fee_records_student_due_paid'):
        op.drop_index('ix_fee_records_student_due_paid', table_name='fee_records')

    if _table_exists(inspector, 'student_batch_map') and _index_exists(inspector, 'student_batch_map', 'ix_student_batch_map_batch_active'):
        op.drop_index('ix_student_batch_map_batch_active', table_name='student_batch_map')

    if _table_exists(inspector, 'batch_schedules') and _index_exists(inspector, 'batch_schedules', 'ix_batch_schedules_weekday_start_time'):
        op.drop_index('ix_batch_schedules_weekday_start_time', table_name='batch_schedules')

    if _table_exists(inspector, 'calendar_overrides') and _index_exists(inspector, 'calendar_overrides', 'ix_calendar_overrides_batch_date'):
        op.drop_index('ix_calendar_overrides_batch_date', table_name='calendar_overrides')

    inspector = sa.inspect(bind)
    if _table_exists(inspector, 'calendar_overrides'):
        op.drop_table('calendar_overrides')
