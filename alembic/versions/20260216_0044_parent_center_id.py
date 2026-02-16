"""parent center ownership

Revision ID: 20260216_0044
Revises: 20260216_0043
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260216_0044"
down_revision = "20260216_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "parents" not in tables:
        return

    columns = {c["name"] for c in inspector.get_columns("parents")}
    if "center_id" not in columns:
        with op.batch_alter_table("parents") as batch_op:
            batch_op.add_column(sa.Column("center_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key("fk_parents_center_id_centers", "centers", ["center_id"], ["id"])

    op.execute(
        """
        UPDATE parents
        SET center_id = COALESCE(
            (
                SELECT s.center_id
                FROM parent_student_map psm
                JOIN students s ON s.id = psm.student_id
                WHERE psm.parent_id = parents.id
                ORDER BY psm.id ASC
                LIMIT 1
            ),
            1
        )
        WHERE center_id IS NULL
        """
    )

    with op.batch_alter_table("parents") as batch_op:
        batch_op.alter_column("center_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_index("ix_parents_center_id", ["center_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "parents" not in tables:
        return

    columns = {c["name"] for c in inspector.get_columns("parents")}
    if "center_id" not in columns:
        return

    with op.batch_alter_table("parents") as batch_op:
        try:
            batch_op.drop_index("ix_parents_center_id")
        except Exception:
            pass
        try:
            batch_op.drop_constraint("fk_parents_center_id_centers", type_="foreignkey")
        except Exception:
            pass
        batch_op.drop_column("center_id")
