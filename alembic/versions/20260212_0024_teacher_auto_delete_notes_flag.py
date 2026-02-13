"""teacher profile flag for note expiry auto-delete

Revision ID: 20260212_0024
Revises: 20260212_0023
Create Date: 2026-02-12 12:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260212_0024'
down_revision = '20260212_0023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    auth_cols = {col['name'] for col in inspector.get_columns('auth_users')}
    if 'enable_auto_delete_notes_on_expiry' not in auth_cols:
        op.add_column(
            'auth_users',
            sa.Column(
                'enable_auto_delete_notes_on_expiry',
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    op.drop_column('auth_users', 'enable_auto_delete_notes_on_expiry')
