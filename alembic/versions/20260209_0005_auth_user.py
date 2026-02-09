"""add auth_users for otp login

Revision ID: 20260209_0005
Revises: 20260209_0004
Create Date: 2026-02-09 00:05:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '20260209_0005'
down_revision = '20260209_0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if 'auth_users' not in tables:
        op.create_table(
            'auth_users',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('phone', sa.String(length=20), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False, server_default='teacher'),
            sa.Column('last_otp', sa.String(length=255), nullable=False, server_default=''),
            sa.Column('otp_created_at', sa.DateTime(), nullable=True),
        )

    indexes = {idx['name'] for idx in inspector.get_indexes('auth_users')}
    if 'ix_auth_users_id' not in indexes:
        op.create_index('ix_auth_users_id', 'auth_users', ['id'])
    if 'ix_auth_users_phone' not in indexes:
        op.create_index('ix_auth_users_phone', 'auth_users', ['phone'], unique=True)
    if 'ix_auth_users_role' not in indexes:
        op.create_index('ix_auth_users_role', 'auth_users', ['role'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if 'auth_users' not in tables:
        return

    indexes = {idx['name'] for idx in inspector.get_indexes('auth_users')}
    if 'ix_auth_users_role' in indexes:
        op.drop_index('ix_auth_users_role', table_name='auth_users')
    if 'ix_auth_users_phone' in indexes:
        op.drop_index('ix_auth_users_phone', table_name='auth_users')
    if 'ix_auth_users_id' in indexes:
        op.drop_index('ix_auth_users_id', table_name='auth_users')
    op.drop_table('auth_users')
