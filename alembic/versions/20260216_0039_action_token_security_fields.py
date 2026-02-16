"""add action token security fields

Revision ID: 20260216_0039
Revises: 20260216_0038
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260216_0039"
down_revision = "20260216_0038"
branch_labels = None
depends_on = None


def _add_col_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = {c["name"] for c in inspector.get_columns(table)}
    if column.name not in cols:
        op.add_column(table, column)


def _create_index_if_missing(table: str, name: str, columns: list[str], unique: bool = False) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes(table)}
    if name not in indexes:
        op.create_index(name, table, columns, unique=unique)


def upgrade() -> None:
    _add_col_if_missing("action_tokens", sa.Column("expected_role", sa.String(length=20), nullable=False, server_default="teacher"))
    _add_col_if_missing("action_tokens", sa.Column("center_id", sa.Integer(), nullable=False, server_default="1"))
    _add_col_if_missing("action_tokens", sa.Column("consumed_at", sa.DateTime(), nullable=True))
    _add_col_if_missing("action_tokens", sa.Column("issued_ip", sa.String(length=64), nullable=False, server_default=""))
    _add_col_if_missing("action_tokens", sa.Column("issued_user_agent", sa.String(length=512), nullable=False, server_default=""))

    _create_index_if_missing("action_tokens", "ix_action_tokens_expected_role", ["expected_role"])
    _create_index_if_missing("action_tokens", "ix_action_tokens_center_id", ["center_id"])
    _create_index_if_missing("action_tokens", "ix_action_tokens_consumed_at", ["consumed_at"])
    _create_index_if_missing("action_tokens", "ix_action_tokens_expires_at", ["expires_at"])
    _create_index_if_missing("action_tokens", "ix_action_tokens_consumed", ["consumed"])
    _create_index_if_missing("action_tokens", "ix_action_tokens_token_hash", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_action_tokens_consumed_at", table_name="action_tokens")
    op.drop_index("ix_action_tokens_center_id", table_name="action_tokens")
    op.drop_index("ix_action_tokens_expected_role", table_name="action_tokens")
    op.drop_column("action_tokens", "issued_user_agent")
    op.drop_column("action_tokens", "issued_ip")
    op.drop_column("action_tokens", "consumed_at")
    op.drop_column("action_tokens", "center_id")
    op.drop_column("action_tokens", "expected_role")
