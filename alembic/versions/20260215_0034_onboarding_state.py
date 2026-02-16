"""add onboarding state table for guided saas onboarding

Revision ID: 20260215_0034
Revises: 20260215_0033
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260215_0034"
down_revision = "20260215_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "onboarding_states" not in tables:
        op.create_table(
            "onboarding_states",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("center_id", sa.Integer(), nullable=False),
            sa.Column("reserved_slug", sa.String(length=120), nullable=False),
            sa.Column("setup_token", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="in_progress"),
            sa.Column("current_step", sa.String(length=40), nullable=False, server_default="center_setup"),
            sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("lock_expires_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["center_id"], ["centers.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("center_id", name="uq_onboarding_states_center_id"),
            sa.UniqueConstraint("reserved_slug", name="uq_onboarding_states_reserved_slug"),
            sa.UniqueConstraint("setup_token"),
        )
        inspector = inspect(bind)

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("onboarding_states")}
    indexes = [
        ("ix_onboarding_states_center_id", ["center_id"], False),
        ("ix_onboarding_states_reserved_slug", ["reserved_slug"], False),
        ("ix_onboarding_states_setup_token", ["setup_token"], True),
        ("ix_onboarding_states_status", ["status"], False),
        ("ix_onboarding_states_current_step", ["current_step"], False),
        ("ix_onboarding_states_is_completed", ["is_completed"], False),
        ("ix_onboarding_states_lock_expires_at", ["lock_expires_at"], False),
        ("ix_onboarding_states_created_at", ["created_at"], False),
        ("ix_onboarding_states_updated_at", ["updated_at"], False),
        ("ix_onboarding_states_status_completed", ["status", "is_completed"], False),
    ]
    for index_name, columns, unique in indexes:
        if index_name not in existing_indexes:
            op.create_index(index_name, "onboarding_states", columns, unique=unique)


def downgrade() -> None:
    op.drop_index("ix_onboarding_states_status_completed", table_name="onboarding_states")
    op.drop_index("ix_onboarding_states_updated_at", table_name="onboarding_states")
    op.drop_index("ix_onboarding_states_created_at", table_name="onboarding_states")
    op.drop_index("ix_onboarding_states_lock_expires_at", table_name="onboarding_states")
    op.drop_index("ix_onboarding_states_is_completed", table_name="onboarding_states")
    op.drop_index("ix_onboarding_states_current_step", table_name="onboarding_states")
    op.drop_index("ix_onboarding_states_status", table_name="onboarding_states")
    op.drop_index("ix_onboarding_states_setup_token", table_name="onboarding_states")
    op.drop_index("ix_onboarding_states_reserved_slug", table_name="onboarding_states")
    op.drop_index("ix_onboarding_states_center_id", table_name="onboarding_states")
    op.drop_table("onboarding_states")
