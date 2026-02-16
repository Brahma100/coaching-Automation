"""time and capacity engine schema

Revision ID: 20260213_0027
Revises: 20260212_0026
Create Date: 2026-02-13 18:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260213_0027'
down_revision = '20260212_0026'
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(col['name'] == column_name for col in inspector.get_columns(table_name))


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(idx['name'] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, 'auth_users'):
        if not _column_exists(inspector, 'auth_users', 'daily_work_start_time'):
            op.add_column(
                'auth_users',
                sa.Column('daily_work_start_time', sa.Time(), nullable=False, server_default='07:00:00'),
            )
        if not _column_exists(inspector, 'auth_users', 'daily_work_end_time'):
            op.add_column(
                'auth_users',
                sa.Column('daily_work_end_time', sa.Time(), nullable=False, server_default='20:00:00'),
            )
        if not _column_exists(inspector, 'auth_users', 'max_daily_hours'):
            op.add_column('auth_users', sa.Column('max_daily_hours', sa.Integer(), nullable=True))
        if not _column_exists(inspector, 'auth_users', 'timezone'):
            op.add_column(
                'auth_users',
                sa.Column('timezone', sa.String(length=60), nullable=False, server_default='Asia/Kolkata'),
            )

    if _table_exists(inspector, 'batches') and not _column_exists(inspector, 'batches', 'max_students'):
        op.add_column('batches', sa.Column('max_students', sa.Integer(), nullable=True))

    inspector = sa.inspect(op.get_bind())
    if not _table_exists(inspector, 'teacher_unavailability'):
        op.create_table(
            'teacher_unavailability',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('teacher_id', sa.Integer(), nullable=False),
            sa.Column('date', sa.Date(), nullable=False),
            sa.Column('start_time', sa.Time(), nullable=False),
            sa.Column('end_time', sa.Time(), nullable=False),
            sa.Column('reason', sa.String(length=255), nullable=False, server_default=''),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.PrimaryKeyConstraint('id'),
        )

    inspector = sa.inspect(op.get_bind())
    if not _index_exists(inspector, 'teacher_unavailability', 'ix_teacher_unavailability_teacher_date'):
        op.create_index('ix_teacher_unavailability_teacher_date', 'teacher_unavailability', ['teacher_id', 'date'])
    if not _index_exists(inspector, 'teacher_unavailability', 'ix_teacher_unavailability_teacher_date_start'):
        op.create_index('ix_teacher_unavailability_teacher_date_start', 'teacher_unavailability', ['teacher_id', 'date', 'start_time'])
    if not _index_exists(inspector, 'teacher_unavailability', 'ix_teacher_unavailability_teacher_id'):
        op.create_index('ix_teacher_unavailability_teacher_id', 'teacher_unavailability', ['teacher_id'])
    if not _index_exists(inspector, 'teacher_unavailability', 'ix_teacher_unavailability_date'):
        op.create_index('ix_teacher_unavailability_date', 'teacher_unavailability', ['date'])
    if not _index_exists(inspector, 'teacher_unavailability', 'ix_teacher_unavailability_id'):
        op.create_index('ix_teacher_unavailability_id', 'teacher_unavailability', ['id'])
    if not _index_exists(inspector, 'auth_users', 'ix_auth_users_timezone'):
        op.create_index('ix_auth_users_timezone', 'auth_users', ['timezone'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _index_exists(inspector, 'auth_users', 'ix_auth_users_timezone'):
        op.drop_index('ix_auth_users_timezone', table_name='auth_users')

    inspector = sa.inspect(op.get_bind())
    if _index_exists(inspector, 'teacher_unavailability', 'ix_teacher_unavailability_id'):
        op.drop_index('ix_teacher_unavailability_id', table_name='teacher_unavailability')
    if _index_exists(inspector, 'teacher_unavailability', 'ix_teacher_unavailability_date'):
        op.drop_index('ix_teacher_unavailability_date', table_name='teacher_unavailability')
    if _index_exists(inspector, 'teacher_unavailability', 'ix_teacher_unavailability_teacher_id'):
        op.drop_index('ix_teacher_unavailability_teacher_id', table_name='teacher_unavailability')
    if _index_exists(inspector, 'teacher_unavailability', 'ix_teacher_unavailability_teacher_date_start'):
        op.drop_index('ix_teacher_unavailability_teacher_date_start', table_name='teacher_unavailability')
    if _index_exists(inspector, 'teacher_unavailability', 'ix_teacher_unavailability_teacher_date'):
        op.drop_index('ix_teacher_unavailability_teacher_date', table_name='teacher_unavailability')

    inspector = sa.inspect(op.get_bind())
    if _table_exists(inspector, 'teacher_unavailability'):
        op.drop_table('teacher_unavailability')

    inspector = sa.inspect(op.get_bind())
    if _table_exists(inspector, 'auth_users'):
        if _column_exists(inspector, 'auth_users', 'timezone'):
            op.drop_column('auth_users', 'timezone')
        if _column_exists(inspector, 'auth_users', 'max_daily_hours'):
            op.drop_column('auth_users', 'max_daily_hours')
        if _column_exists(inspector, 'auth_users', 'daily_work_end_time'):
            op.drop_column('auth_users', 'daily_work_end_time')
        if _column_exists(inspector, 'auth_users', 'daily_work_start_time'):
            op.drop_column('auth_users', 'daily_work_start_time')
