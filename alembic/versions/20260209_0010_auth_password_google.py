"""auth password + google identity fields

Revision ID: 20260209_0010
Revises: 20260209_0009
Create Date: 2026-02-09 00:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260209_0010'
down_revision = '20260209_0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col['name'] for col in inspector.get_columns('auth_users')}
    if 'password_hash' not in columns:
        op.add_column('auth_users', sa.Column('password_hash', sa.String(length=255), nullable=False, server_default=''))
    if 'google_sub' not in columns:
        op.add_column('auth_users', sa.Column('google_sub', sa.String(length=255), nullable=False, server_default=''))
    idx_names = {idx['name'] for idx in inspector.get_indexes('auth_users')}
    if 'ix_auth_users_google_sub' not in idx_names:
        op.create_index('ix_auth_users_google_sub', 'auth_users', ['google_sub'])


def downgrade() -> None:
    op.drop_index('ix_auth_users_google_sub', table_name='auth_users')
    op.drop_column('auth_users', 'google_sub')
    op.drop_column('auth_users', 'password_hash')
