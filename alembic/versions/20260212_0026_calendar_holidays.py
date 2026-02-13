"""calendar holidays table

Revision ID: 20260212_0026
Revises: 20260212_0025
Create Date: 2026-02-12 23:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260212_0026'
down_revision = '20260212_0025'
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(idx['name'] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, 'calendar_holidays'):
        op.create_table(
            'calendar_holidays',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('country_code', sa.String(length=2), nullable=False, server_default='IN'),
            sa.Column('holiday_date', sa.Date(), nullable=False),
            sa.Column('year', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=180), nullable=False),
            sa.Column('local_name', sa.String(length=180), nullable=True),
            sa.Column('source', sa.String(length=40), nullable=False, server_default='nager'),
            sa.Column('is_national', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('country_code', 'holiday_date', 'name', name='uq_calendar_holidays_country_date_name'),
        )

    inspector = sa.inspect(op.get_bind())
    if not _index_exists(inspector, 'calendar_holidays', 'ix_calendar_holidays_country_date'):
        op.create_index('ix_calendar_holidays_country_date', 'calendar_holidays', ['country_code', 'holiday_date'])
    if not _index_exists(inspector, 'calendar_holidays', 'ix_calendar_holidays_year_country'):
        op.create_index('ix_calendar_holidays_year_country', 'calendar_holidays', ['year', 'country_code'])
    if not _index_exists(inspector, 'calendar_holidays', 'ix_calendar_holidays_country_code'):
        op.create_index('ix_calendar_holidays_country_code', 'calendar_holidays', ['country_code'])
    if not _index_exists(inspector, 'calendar_holidays', 'ix_calendar_holidays_holiday_date'):
        op.create_index('ix_calendar_holidays_holiday_date', 'calendar_holidays', ['holiday_date'])
    if not _index_exists(inspector, 'calendar_holidays', 'ix_calendar_holidays_year'):
        op.create_index('ix_calendar_holidays_year', 'calendar_holidays', ['year'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _index_exists(inspector, 'calendar_holidays', 'ix_calendar_holidays_year'):
        op.drop_index('ix_calendar_holidays_year', table_name='calendar_holidays')
    if _index_exists(inspector, 'calendar_holidays', 'ix_calendar_holidays_holiday_date'):
        op.drop_index('ix_calendar_holidays_holiday_date', table_name='calendar_holidays')
    if _index_exists(inspector, 'calendar_holidays', 'ix_calendar_holidays_country_code'):
        op.drop_index('ix_calendar_holidays_country_code', table_name='calendar_holidays')
    if _index_exists(inspector, 'calendar_holidays', 'ix_calendar_holidays_year_country'):
        op.drop_index('ix_calendar_holidays_year_country', table_name='calendar_holidays')
    if _index_exists(inspector, 'calendar_holidays', 'ix_calendar_holidays_country_date'):
        op.drop_index('ix_calendar_holidays_country_date', table_name='calendar_holidays')

    inspector = sa.inspect(op.get_bind())
    if _table_exists(inspector, 'calendar_holidays'):
        op.drop_table('calendar_holidays')
