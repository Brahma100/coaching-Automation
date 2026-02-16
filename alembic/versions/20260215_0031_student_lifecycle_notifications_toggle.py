"""add student lifecycle notification toggle to rule configs

Revision ID: 20260215_0031
Revises: 20260215_0030
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260215_0031"
down_revision = "20260215_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [row["name"] for row in inspector.get_columns("rule_configs")]
    if "enable_student_lifecycle_notifications" not in columns:
        op.add_column(
            "rule_configs",
            sa.Column("enable_student_lifecycle_notifications", sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    op.drop_column("rule_configs", "enable_student_lifecycle_notifications")
