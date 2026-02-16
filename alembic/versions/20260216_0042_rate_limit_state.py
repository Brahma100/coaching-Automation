"""rate limiting state table

Revision ID: 20260216_0042
Revises: 20260216_0041
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260216_0042"
down_revision = "20260216_0041"
branch_labels = None
depends_on = None


def _indexes(table: str) -> set[str]:
    bind = op.get_bind()
    return {i["name"] for i in inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "rate_limit_states" not in set(inspector.get_table_names()):
        op.create_table(
            "rate_limit_states",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("center_id", sa.Integer(), sa.ForeignKey("centers.id"), nullable=False, server_default="1"),
            sa.Column("scope_type", sa.String(length=20), nullable=False, server_default="user"),
            sa.Column("scope_key", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("action_name", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("window_start", sa.DateTime(), nullable=False),
            sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("center_id", "scope_type", "scope_key", "action_name", name="uq_rate_limit_scope_action"),
        )
        op.create_index("ix_rate_limit_states_center_id", "rate_limit_states", ["center_id"])
        op.create_index("ix_rate_limit_states_scope_type", "rate_limit_states", ["scope_type"])
        op.create_index("ix_rate_limit_states_scope_key", "rate_limit_states", ["scope_key"])
        op.create_index("ix_rate_limit_states_action_name", "rate_limit_states", ["action_name"])
        op.create_index("ix_rate_limit_states_window_start", "rate_limit_states", ["window_start"])
        op.create_index(
            "ix_rate_limit_scope_action",
            "rate_limit_states",
            ["center_id", "scope_type", "scope_key", "action_name"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "rate_limit_states" in set(inspector.get_table_names()):
        table_indexes = _indexes("rate_limit_states")
        for name in (
            "ix_rate_limit_scope_action",
            "ix_rate_limit_states_window_start",
            "ix_rate_limit_states_action_name",
            "ix_rate_limit_states_scope_key",
            "ix_rate_limit_states_scope_type",
            "ix_rate_limit_states_center_id",
        ):
            if name in table_indexes:
                op.drop_index(name, table_name="rate_limit_states")
        op.drop_table("rate_limit_states")
