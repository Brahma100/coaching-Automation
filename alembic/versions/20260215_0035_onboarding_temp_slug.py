"""add temp_slug column to onboarding state

Revision ID: 20260215_0035
Revises: 20260215_0034
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260215_0035"
down_revision = "20260215_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("onboarding_states")}
    if "temp_slug" not in columns:
        op.add_column("onboarding_states", sa.Column("temp_slug", sa.String(length=120), nullable=False, server_default=""))
    index_names = {idx["name"] for idx in inspector.get_indexes("onboarding_states")}
    if "ix_onboarding_states_temp_slug" not in index_names:
        op.create_index("ix_onboarding_states_temp_slug", "onboarding_states", ["temp_slug"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_onboarding_states_temp_slug", table_name="onboarding_states")
    op.drop_column("onboarding_states", "temp_slug")
