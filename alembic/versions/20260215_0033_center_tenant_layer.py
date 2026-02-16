"""add center tenant layer and center_id scoping columns

Revision ID: 20260215_0033
Revises: 20260215_0032
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = "20260215_0033"
down_revision = "20260215_0032"
branch_labels = None
depends_on = None


def _ensure_default_center() -> int:
    bind = op.get_bind()
    row = bind.execute(text("SELECT id FROM centers WHERE slug = 'default-center' LIMIT 1")).fetchone()
    if row:
        return int(row[0])
    owner_row = bind.execute(text("SELECT id FROM auth_users ORDER BY id ASC LIMIT 1")).fetchone()
    owner_id = int(owner_row[0]) if owner_row else None
    bind.execute(
        text(
            "INSERT INTO centers (name, slug, owner_user_id, timezone, created_at) "
            "VALUES (:name, :slug, :owner_user_id, :timezone, CURRENT_TIMESTAMP)"
        ),
        {
            "name": "default-center",
            "slug": "default-center",
            "owner_user_id": owner_id,
            "timezone": "Asia/Kolkata",
        },
    )
    row = bind.execute(text("SELECT id FROM centers WHERE slug = 'default-center' LIMIT 1")).fetchone()
    return int(row[0])


def _add_center_column_if_missing(table_name: str) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {c["name"] for c in inspector.get_columns(table_name)}
    if "center_id" not in columns:
        op.add_column(table_name, sa.Column("center_id", sa.Integer(), nullable=True))


def _backfill_center_id(table_name: str, default_center_id: int) -> None:
    bind = op.get_bind()
    bind.execute(
        text(f"UPDATE {table_name} SET center_id = :center_id WHERE center_id IS NULL"),
        {"center_id": int(default_center_id)},
    )


def _ensure_index(table_name: str, index_name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    index_names = {idx["name"] for idx in inspector.get_indexes(table_name)}
    if index_name not in index_names:
        op.create_index(index_name, table_name, columns, unique=False)


def _ensure_fk_to_centers(table_name: str, fk_name: str) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    fk_names = {fk.get("name") for fk in inspector.get_foreign_keys(table_name)}
    if fk_name in fk_names:
        return
    with op.batch_alter_table(table_name) as batch:
        batch.create_foreign_key(fk_name, "centers", ["center_id"], ["id"])


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "centers" not in tables:
        op.create_table(
            "centers",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=180), nullable=False),
            sa.Column("slug", sa.String(length=120), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("timezone", sa.String(length=60), nullable=False, server_default="Asia/Kolkata"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["owner_user_id"], ["auth_users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug", name="uq_centers_slug"),
        )
        op.create_index("ix_centers_slug", "centers", ["slug"], unique=True)

    default_center_id = _ensure_default_center()

    scoped_tables = [
        "auth_users",
        "batches",
        "students",
        "class_sessions",
        "teacher_batch_map",
        "pending_actions",
        "notes",
    ]
    for table_name in scoped_tables:
        _add_center_column_if_missing(table_name)
        _backfill_center_id(table_name, default_center_id)
        with op.batch_alter_table(table_name) as batch:
            batch.alter_column("center_id", existing_type=sa.Integer(), nullable=False)
        _ensure_fk_to_centers(table_name, f"fk_{table_name}_center_id_centers")
        _ensure_index(table_name, f"ix_{table_name}_center_id", ["center_id"])
        _ensure_index(table_name, f"ix_{table_name}_center_id_id", ["center_id", "id"])


def downgrade() -> None:
    scoped_tables = [
        "notes",
        "pending_actions",
        "teacher_batch_map",
        "class_sessions",
        "students",
        "batches",
        "auth_users",
    ]
    for table_name in scoped_tables:
        bind = op.get_bind()
        inspector = inspect(bind)
        fk_name = f"fk_{table_name}_center_id_centers"
        fk_names = {fk.get("name") for fk in inspector.get_foreign_keys(table_name)}
        with op.batch_alter_table(table_name) as batch:
            if fk_name in fk_names:
                batch.drop_constraint(fk_name, type_="foreignkey")
            batch.drop_column("center_id")
    op.drop_table("centers")
