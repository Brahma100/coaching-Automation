"""add calendar phase1 fields

Revision ID: 20260211_0021
Revises: 20260211_0020_calendar_schema_enhancements
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa


revision = '20260211_0021'
down_revision = '20260211_0020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('batches', sa.Column('location', sa.String(length=255), nullable=True))
    op.add_column('batches', sa.Column('max_students', sa.Integer(), nullable=True))
    op.add_column('batches', sa.Column('is_online', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.add_column('batches', sa.Column('meeting_link', sa.String(length=500), nullable=True))

    op.add_column('auth_users', sa.Column('calendar_view_preference', sa.String(length=20), nullable=False, server_default='week'))
    op.add_column('auth_users', sa.Column('calendar_snap_minutes', sa.Integer(), nullable=False, server_default='15'))
    op.add_column('auth_users', sa.Column('enable_live_mode_auto_open', sa.Boolean(), nullable=False, server_default=sa.text('1')))
    op.add_column('auth_users', sa.Column('default_event_color', sa.String(length=20), nullable=True))

    op.alter_column('batches', 'is_online', server_default=None)
    op.alter_column('auth_users', 'calendar_view_preference', server_default=None)
    op.alter_column('auth_users', 'calendar_snap_minutes', server_default=None)
    op.alter_column('auth_users', 'enable_live_mode_auto_open', server_default=None)


def downgrade() -> None:
    op.drop_column('auth_users', 'default_event_color')
    op.drop_column('auth_users', 'enable_live_mode_auto_open')
    op.drop_column('auth_users', 'calendar_snap_minutes')
    op.drop_column('auth_users', 'calendar_view_preference')

    op.drop_column('batches', 'meeting_link')
    op.drop_column('batches', 'is_online')
    op.drop_column('batches', 'max_students')
    op.drop_column('batches', 'location')
