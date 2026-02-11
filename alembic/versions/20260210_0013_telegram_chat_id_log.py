"""telegram chat id in communication logs

Revision ID: 20260210_0013
Revises: 20260210_0012
Create Date: 2026-02-10 00:13:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260210_0013'
down_revision = '20260210_0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {col['name'] for col in inspector.get_columns('communication_logs')}
    if 'telegram_chat_id' not in cols:
        op.add_column('communication_logs', sa.Column('telegram_chat_id', sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column('communication_logs', 'telegram_chat_id')
