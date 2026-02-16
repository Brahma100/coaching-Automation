"""add teacher batch mapping table for scoped access

Revision ID: 20260215_0032
Revises: 20260215_0031
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260215_0032"
down_revision = "20260215_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "teacher_batch_map" in tables:
        return

    op.create_table(
        "teacher_batch_map",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["teacher_id"], ["auth_users.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("teacher_id", "batch_id", name="uq_teacher_batch_map_teacher_batch"),
    )
    op.create_index("ix_teacher_batch_map_teacher_batch", "teacher_batch_map", ["teacher_id", "batch_id"], unique=False)
    op.create_index("ix_teacher_batch_map_teacher_id", "teacher_batch_map", ["teacher_id"], unique=False)
    op.create_index("ix_teacher_batch_map_batch_id", "teacher_batch_map", ["batch_id"], unique=False)
    op.create_index("ix_teacher_batch_map_is_primary", "teacher_batch_map", ["is_primary"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_teacher_batch_map_is_primary", table_name="teacher_batch_map")
    op.drop_index("ix_teacher_batch_map_batch_id", table_name="teacher_batch_map")
    op.drop_index("ix_teacher_batch_map_teacher_id", table_name="teacher_batch_map")
    op.drop_index("ix_teacher_batch_map_teacher_batch", table_name="teacher_batch_map")
    op.drop_table("teacher_batch_map")
