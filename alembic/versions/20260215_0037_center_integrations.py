"""add center integrations table

Revision ID: 20260215_0037
Revises: 20260215_0036
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260215_0037"
down_revision = "20260215_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "center_integrations" not in tables:
        op.create_table(
            "center_integrations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("center_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=40), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="disconnected"),
            sa.Column("config_json", sa.Text(), nullable=False, server_default=""),
            sa.Column("connected_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["center_id"], ["centers.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("center_id", "provider", name="uq_center_integrations_center_provider"),
        )
        inspector = inspect(bind)

    existing_indexes = {idx["name"] for idx in inspector.get_indexes("center_integrations")}
    indexes = [
        ("ix_center_integrations_id", ["id"], False),
        ("ix_center_integrations_center_id", ["center_id"], False),
        ("ix_center_integrations_provider", ["provider"], False),
        ("ix_center_integrations_status", ["status"], False),
        ("ix_center_integrations_connected_at", ["connected_at"], False),
        ("ix_center_integrations_created_at", ["created_at"], False),
        ("ix_center_integrations_updated_at", ["updated_at"], False),
        ("ix_center_integrations_center_provider", ["center_id", "provider"], False),
    ]
    for index_name, columns, unique in indexes:
        if index_name not in existing_indexes:
            op.create_index(index_name, "center_integrations", columns, unique=unique)


def downgrade() -> None:
    op.drop_index("ix_center_integrations_center_provider", table_name="center_integrations")
    op.drop_index("ix_center_integrations_updated_at", table_name="center_integrations")
    op.drop_index("ix_center_integrations_created_at", table_name="center_integrations")
    op.drop_index("ix_center_integrations_connected_at", table_name="center_integrations")
    op.drop_index("ix_center_integrations_status", table_name="center_integrations")
    op.drop_index("ix_center_integrations_provider", table_name="center_integrations")
    op.drop_index("ix_center_integrations_center_id", table_name="center_integrations")
    op.drop_index("ix_center_integrations_id", table_name="center_integrations")
    op.drop_table("center_integrations")
