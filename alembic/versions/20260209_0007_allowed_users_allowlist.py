"""add allowed_users allowlist table

Revision ID: 20260209_0007
Revises: 20260209_0006
Create Date: 2026-02-09 00:07:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '20260209_0007'
down_revision = '20260209_0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if 'allowed_users' not in tables:
        op.create_table(
            'allowed_users',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('phone', sa.String(length=20), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False, server_default='teacher'),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='invited'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )

    indexes = {idx['name'] for idx in inspector.get_indexes('allowed_users')}
    if 'ix_allowed_users_id' not in indexes:
        op.create_index('ix_allowed_users_id', 'allowed_users', ['id'])
    if 'ix_allowed_users_phone' not in indexes:
        op.create_index('ix_allowed_users_phone', 'allowed_users', ['phone'], unique=True)
    if 'ix_allowed_users_role' not in indexes:
        op.create_index('ix_allowed_users_role', 'allowed_users', ['role'])
    if 'ix_allowed_users_status' not in indexes:
        op.create_index('ix_allowed_users_status', 'allowed_users', ['status'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if 'allowed_users' not in tables:
        return

    indexes = {idx['name'] for idx in inspector.get_indexes('allowed_users')}
    if 'ix_allowed_users_status' in indexes:
        op.drop_index('ix_allowed_users_status', table_name='allowed_users')
    if 'ix_allowed_users_role' in indexes:
        op.drop_index('ix_allowed_users_role', table_name='allowed_users')
    if 'ix_allowed_users_phone' in indexes:
        op.drop_index('ix_allowed_users_phone', table_name='allowed_users')
    if 'ix_allowed_users_id' in indexes:
        op.drop_index('ix_allowed_users_id', table_name='allowed_users')
    op.drop_table('allowed_users')
