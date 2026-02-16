"""automation reliability fields and dead-letter log

Revision ID: 20260216_0040
Revises: 20260216_0039
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260216_0040"
down_revision = "20260216_0039"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _indexes(table: str) -> set[str]:
    bind = op.get_bind()
    return {i["name"] for i in inspect(bind).get_indexes(table)}


def _add_col_if_missing(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        op.add_column(table, column)


def _create_index_if_missing(table: str, name: str, columns: list[str], unique: bool = False) -> None:
    if name not in _indexes(table):
        op.create_index(name, table, columns, unique=unique)


def upgrade() -> None:
    _add_col_if_missing(
        "class_sessions",
        sa.Column("post_class_error", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _create_index_if_missing("class_sessions", "ix_class_sessions_post_class_error", ["post_class_error"])

    _add_col_if_missing(
        "communication_logs",
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_col_if_missing(
        "communication_logs",
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
    )
    _add_col_if_missing(
        "communication_logs",
        sa.Column("delivery_status", sa.String(length=30), nullable=False, server_default="pending"),
    )
    _create_index_if_missing("communication_logs", "ix_communication_logs_last_attempt_at", ["last_attempt_at"])
    _create_index_if_missing("communication_logs", "ix_communication_logs_delivery_status", ["delivery_status"])

    bind = op.get_bind()
    inspector = inspect(bind)
    if "automation_failure_logs" not in set(inspector.get_table_names()):
        op.create_table(
            "automation_failure_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("center_id", sa.Integer(), sa.ForeignKey("centers.id"), nullable=False, server_default="1"),
            sa.Column("job_name", sa.String(length=80), nullable=False),
            sa.Column("entity_type", sa.String(length=50), nullable=False, server_default=""),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_automation_failure_logs_center_id", "automation_failure_logs", ["center_id"])
        op.create_index("ix_automation_failure_logs_job_name", "automation_failure_logs", ["job_name"])
        op.create_index("ix_automation_failure_logs_entity_type", "automation_failure_logs", ["entity_type"])
        op.create_index("ix_automation_failure_logs_entity_id", "automation_failure_logs", ["entity_id"])
        op.create_index("ix_automation_failure_logs_created_at", "automation_failure_logs", ["created_at"])
        op.create_index(
            "ix_automation_failure_logs_center_job_created",
            "automation_failure_logs",
            ["center_id", "job_name", "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "automation_failure_logs" in set(inspector.get_table_names()):
        op.drop_table("automation_failure_logs")

    if "ix_communication_logs_delivery_status" in _indexes("communication_logs"):
        op.drop_index("ix_communication_logs_delivery_status", table_name="communication_logs")
    if "ix_communication_logs_last_attempt_at" in _indexes("communication_logs"):
        op.drop_index("ix_communication_logs_last_attempt_at", table_name="communication_logs")
    cols = _columns("communication_logs")
    if "delivery_status" in cols:
        op.drop_column("communication_logs", "delivery_status")
    if "last_attempt_at" in cols:
        op.drop_column("communication_logs", "last_attempt_at")
    if "delivery_attempts" in cols:
        op.drop_column("communication_logs", "delivery_attempts")

    if "ix_class_sessions_post_class_error" in _indexes("class_sessions"):
        op.drop_index("ix_class_sessions_post_class_error", table_name="class_sessions")
    if "post_class_error" in _columns("class_sessions"):
        op.drop_column("class_sessions", "post_class_error")
