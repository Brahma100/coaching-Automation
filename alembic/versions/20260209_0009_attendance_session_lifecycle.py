"""attendance session lifecycle and auto-close support

Revision ID: 20260209_0009
Revises: 20260209_0008
Create Date: 2026-02-09 00:09:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260209_0009'
down_revision = '20260209_0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    class_session_columns = {col['name'] for col in inspector.get_columns('class_sessions')}
    if 'closed_at' not in class_session_columns:
        op.add_column('class_sessions', sa.Column('closed_at', sa.DateTime(), nullable=True))

    idx_names = {idx['name'] for idx in inspector.get_indexes('class_sessions')}
    if 'ix_class_sessions_closed_at' not in idx_names:
        op.create_index('ix_class_sessions_closed_at', 'class_sessions', ['closed_at'])


def downgrade() -> None:
    op.drop_index('ix_class_sessions_closed_at', table_name='class_sessions')
    op.drop_column('class_sessions', 'closed_at')
