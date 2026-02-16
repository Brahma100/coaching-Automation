"""add class_sessions.post_class_processed_at

Revision ID: 20260216_0038
Revises: 20260215_0037
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260216_0038"
down_revision = "20260215_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("class_sessions")}
    if "post_class_processed_at" not in columns:
        op.add_column("class_sessions", sa.Column("post_class_processed_at", sa.DateTime(), nullable=True))
    indexes = {idx["name"] for idx in inspector.get_indexes("class_sessions")}
    if "ix_class_sessions_post_class_processed_at" not in indexes:
        op.create_index("ix_class_sessions_post_class_processed_at", "class_sessions", ["post_class_processed_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_class_sessions_post_class_processed_at", table_name="class_sessions")
    op.drop_column("class_sessions", "post_class_processed_at")
