"""teacher profile ui toast duration

Revision ID: 20260212_0025
Revises: 20260212_0024
Create Date: 2026-02-12 14:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260212_0025'
down_revision = '20260212_0024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    auth_cols = {col['name'] for col in inspector.get_columns('auth_users')}
    if 'ui_toast_duration_seconds' not in auth_cols:
        op.add_column(
            'auth_users',
            sa.Column('ui_toast_duration_seconds', sa.Integer(), nullable=False, server_default='5'),
        )


def downgrade() -> None:
    op.drop_column('auth_users', 'ui_toast_duration_seconds')
