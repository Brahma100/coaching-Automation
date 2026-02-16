"""auth user telegram link

Revision ID: 20260215_0030
Revises: 20260214_0029
Create Date: 2026-02-15 14:05:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260215_0030'
down_revision = '20260214_0029'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("auth_users")}
    if "telegram_chat_id" not in columns:
        op.add_column("auth_users", sa.Column("telegram_chat_id", sa.String(length=80), nullable=False, server_default=""))
    indexes = {idx["name"] for idx in inspector.get_indexes("auth_users")}
    if "ix_auth_users_telegram_chat_id" not in indexes:
        op.create_index("ix_auth_users_telegram_chat_id", "auth_users", ["telegram_chat_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_auth_users_telegram_chat_id", table_name="auth_users")
    op.drop_column("auth_users", "telegram_chat_id")
