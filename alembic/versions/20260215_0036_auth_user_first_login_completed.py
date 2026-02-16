"""add first_login_completed to auth users

Revision ID: 20260215_0036
Revises: 20260215_0035
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = "20260215_0036"
down_revision = "20260215_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("auth_users")}
    if "first_login_completed" not in columns:
        op.add_column(
            "auth_users",
            sa.Column("first_login_completed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
    index_names = {idx["name"] for idx in inspector.get_indexes("auth_users")}
    if "ix_auth_users_first_login_completed" not in index_names:
        op.create_index("ix_auth_users_first_login_completed", "auth_users", ["first_login_completed"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_auth_users_first_login_completed", table_name="auth_users")
    op.drop_column("auth_users", "first_login_completed")
