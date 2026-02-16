"""provider circuit breaker state table

Revision ID: 20260216_0041
Revises: 20260216_0040
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260216_0041"
down_revision = "20260216_0040"
branch_labels = None
depends_on = None


def _indexes(table: str) -> set[str]:
    bind = op.get_bind()
    return {i["name"] for i in inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "provider_circuit_states" not in set(inspector.get_table_names()):
        op.create_table(
            "provider_circuit_states",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("center_id", sa.Integer(), sa.ForeignKey("centers.id"), nullable=False, server_default="1"),
            sa.Column("provider_name", sa.String(length=30), nullable=False, server_default="telegram"),
            sa.Column("state", sa.String(length=20), nullable=False, server_default="closed"),
            sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_failure_at", sa.DateTime(), nullable=True),
            sa.Column("last_state_change_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("center_id", "provider_name", name="uq_provider_circuit_center_provider"),
        )
        op.create_index("ix_provider_circuit_states_center_id", "provider_circuit_states", ["center_id"])
        op.create_index("ix_provider_circuit_states_provider_name", "provider_circuit_states", ["provider_name"])
        op.create_index("ix_provider_circuit_states_state", "provider_circuit_states", ["state"])
        op.create_index("ix_provider_circuit_states_last_failure_at", "provider_circuit_states", ["last_failure_at"])
        op.create_index("ix_provider_circuit_states_last_state_change_at", "provider_circuit_states", ["last_state_change_at"])
        op.create_index(
            "ix_provider_circuit_center_provider",
            "provider_circuit_states",
            ["center_id", "provider_name"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "provider_circuit_states" in set(inspector.get_table_names()):
        table_indexes = _indexes("provider_circuit_states")
        for name in (
            "ix_provider_circuit_center_provider",
            "ix_provider_circuit_states_last_state_change_at",
            "ix_provider_circuit_states_last_failure_at",
            "ix_provider_circuit_states_state",
            "ix_provider_circuit_states_provider_name",
            "ix_provider_circuit_states_center_id",
        ):
            if name in table_indexes:
                op.drop_index(name, table_name="provider_circuit_states")
        op.drop_table("provider_circuit_states")
