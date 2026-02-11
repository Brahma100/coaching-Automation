"""Calendar schema enhancements

Revision ID: 20260211_0020
Revises: 20260211_0019
Create Date: 2026-02-11 02:05:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260211_0020'
down_revision = '20260211_0019'
branch_labels = None
depends_on = None


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    return any(idx.get('name') == index_name for idx in inspector.get_indexes(table_name))


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    return any(col.get('name') == column_name for col in inspector.get_columns(table_name))


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, 'auth_users') and not _column_exists(inspector, 'auth_users', 'time_zone'):
        op.add_column('auth_users', sa.Column('time_zone', sa.String(length=60), nullable=False, server_default='UTC'))
    if _table_exists(inspector, 'auth_users') and not _column_exists(inspector, 'auth_users', 'calendar_preferences'):
        op.add_column('auth_users', sa.Column('calendar_preferences', sa.Text(), nullable=False, server_default='{}'))

    if _table_exists(inspector, 'batches') and not _column_exists(inspector, 'batches', 'color_code'):
        op.add_column('batches', sa.Column('color_code', sa.String(length=16), nullable=False, server_default='#2f7bf6'))
    if _table_exists(inspector, 'batches') and not _column_exists(inspector, 'batches', 'default_duration_minutes'):
        op.add_column('batches', sa.Column('default_duration_minutes', sa.Integer(), nullable=False, server_default='60'))

    if _table_exists(inspector, 'students') and not _column_exists(inspector, 'students', 'preferred_contact_method'):
        op.add_column('students', sa.Column('preferred_contact_method', sa.String(length=20), nullable=False, server_default='telegram'))
    if _table_exists(inspector, 'students') and not _column_exists(inspector, 'students', 'language_preference'):
        op.add_column('students', sa.Column('language_preference', sa.String(length=20), nullable=False, server_default='en'))

    if not _table_exists(inspector, 'rooms'):
        op.create_table(
            'rooms',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('institute_id', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('capacity', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('color_code', sa.String(length=16), nullable=False, server_default='#94a3b8'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.PrimaryKeyConstraint('id'),
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, 'batches') and not _column_exists(inspector, 'batches', 'room_id'):
        op.add_column('batches', sa.Column('room_id', sa.Integer(), nullable=True))
        op.create_foreign_key('fk_batches_room_id', 'batches', 'rooms', ['room_id'], ['id'])
        if not _index_exists(inspector, 'batches', 'ix_batches_room_id'):
            op.create_index('ix_batches_room_id', 'batches', ['room_id'])

    if _table_exists(inspector, 'calendar_overrides') and not _column_exists(inspector, 'calendar_overrides', 'institute_id'):
        op.add_column('calendar_overrides', sa.Column('institute_id', sa.Integer(), nullable=False, server_default='0'))
    if _table_exists(inspector, 'calendar_overrides') and not _column_exists(inspector, 'calendar_overrides', 'updated_at'):
        op.add_column('calendar_overrides', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')))

    inspector = sa.inspect(bind)
    if _table_exists(inspector, 'calendar_overrides') and not _index_exists(inspector, 'calendar_overrides', 'ix_calendar_overrides_date_batch'):
        op.create_index('ix_calendar_overrides_date_batch', 'calendar_overrides', ['override_date', 'batch_id'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, 'calendar_overrides') and _index_exists(inspector, 'calendar_overrides', 'ix_calendar_overrides_date_batch'):
        op.drop_index('ix_calendar_overrides_date_batch', table_name='calendar_overrides')

    if _table_exists(inspector, 'calendar_overrides') and _column_exists(inspector, 'calendar_overrides', 'updated_at'):
        op.drop_column('calendar_overrides', 'updated_at')
    if _table_exists(inspector, 'calendar_overrides') and _column_exists(inspector, 'calendar_overrides', 'institute_id'):
        op.drop_column('calendar_overrides', 'institute_id')

    if _table_exists(inspector, 'batches') and _index_exists(inspector, 'batches', 'ix_batches_room_id'):
        op.drop_index('ix_batches_room_id', table_name='batches')
    if _table_exists(inspector, 'batches') and _column_exists(inspector, 'batches', 'room_id'):
        op.drop_constraint('fk_batches_room_id', 'batches', type_='foreignkey')
        op.drop_column('batches', 'room_id')

    if _table_exists(inspector, 'rooms'):
        op.drop_table('rooms')

    if _table_exists(inspector, 'students') and _column_exists(inspector, 'students', 'language_preference'):
        op.drop_column('students', 'language_preference')
    if _table_exists(inspector, 'students') and _column_exists(inspector, 'students', 'preferred_contact_method'):
        op.drop_column('students', 'preferred_contact_method')

    if _table_exists(inspector, 'batches') and _column_exists(inspector, 'batches', 'default_duration_minutes'):
        op.drop_column('batches', 'default_duration_minutes')
    if _table_exists(inspector, 'batches') and _column_exists(inspector, 'batches', 'color_code'):
        op.drop_column('batches', 'color_code')

    if _table_exists(inspector, 'auth_users') and _column_exists(inspector, 'auth_users', 'calendar_preferences'):
        op.drop_column('auth_users', 'calendar_preferences')
    if _table_exists(inspector, 'auth_users') and _column_exists(inspector, 'auth_users', 'time_zone'):
        op.drop_column('auth_users', 'time_zone')
