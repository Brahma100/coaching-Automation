"""admin ops snapshot center isolation

Revision ID: 20260216_0043
Revises: 20260216_0042
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260216_0043"
down_revision = "20260216_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "admin_ops_snapshot" not in tables:
        return

    columns = {c["name"] for c in inspector.get_columns("admin_ops_snapshot")}
    if "center_id" in columns:
        return

    op.create_table(
        "admin_ops_snapshot_v2",
        sa.Column("center_id", sa.Integer(), sa.ForeignKey("centers.id"), nullable=False, server_default="1"),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("center_id", "date"),
    )
    op.create_index("ix_admin_ops_snapshot_v2_center_id", "admin_ops_snapshot_v2", ["center_id"])
    op.create_index("ix_admin_ops_snapshot_v2_date", "admin_ops_snapshot_v2", ["date"])
    op.create_index("ix_admin_ops_snapshot_v2_updated_at", "admin_ops_snapshot_v2", ["updated_at"])

    op.execute(
        """
        INSERT INTO admin_ops_snapshot_v2 (center_id, date, data_json, updated_at)
        SELECT 1 AS center_id, date, data_json, updated_at
        FROM admin_ops_snapshot
        """
    )

    op.drop_table("admin_ops_snapshot")
    op.rename_table("admin_ops_snapshot_v2", "admin_ops_snapshot")
    op.create_index("ix_admin_ops_snapshot_center_id", "admin_ops_snapshot", ["center_id"])
    op.create_index("ix_admin_ops_snapshot_date", "admin_ops_snapshot", ["date"])
    op.create_index("ix_admin_ops_snapshot_updated_at", "admin_ops_snapshot", ["updated_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "admin_ops_snapshot" not in tables:
        return

    columns = {c["name"] for c in inspector.get_columns("admin_ops_snapshot")}
    if "center_id" not in columns:
        return

    op.create_table(
        "admin_ops_snapshot_legacy",
        sa.Column("date", sa.Date(), nullable=False, primary_key=True),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_admin_ops_snapshot_legacy_date", "admin_ops_snapshot_legacy", ["date"])
    op.create_index("ix_admin_ops_snapshot_legacy_updated_at", "admin_ops_snapshot_legacy", ["updated_at"])

    # Keep the earliest center row per day for downgrade compatibility.
    op.execute(
        """
        INSERT INTO admin_ops_snapshot_legacy (date, data_json, updated_at)
        SELECT a.date, a.data_json, a.updated_at
        FROM admin_ops_snapshot a
        JOIN (
            SELECT date, MIN(center_id) AS min_center
            FROM admin_ops_snapshot
            GROUP BY date
        ) b
          ON a.date = b.date AND a.center_id = b.min_center
        """
    )

    op.drop_table("admin_ops_snapshot")
    op.rename_table("admin_ops_snapshot_legacy", "admin_ops_snapshot")
