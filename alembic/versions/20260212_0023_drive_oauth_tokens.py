"""add drive oauth tokens

Revision ID: 20260212_0023
Revises: 20260212_0022
Create Date: 2026-02-12
"""

from alembic import op
import sqlalchemy as sa


revision = '20260212_0023'
down_revision = '20260212_0022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'drive_oauth_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_drive_oauth_token_user'),
    )
    op.create_index('ix_drive_oauth_tokens_id', 'drive_oauth_tokens', ['id'])
    op.create_index('ix_drive_oauth_tokens_user_id', 'drive_oauth_tokens', ['user_id'])
    op.create_index('ix_drive_oauth_tokens_created_at', 'drive_oauth_tokens', ['created_at'])
    op.create_index('ix_drive_oauth_tokens_updated_at', 'drive_oauth_tokens', ['updated_at'])


def downgrade() -> None:
    op.drop_index('ix_drive_oauth_tokens_updated_at', table_name='drive_oauth_tokens')
    op.drop_index('ix_drive_oauth_tokens_created_at', table_name='drive_oauth_tokens')
    op.drop_index('ix_drive_oauth_tokens_user_id', table_name='drive_oauth_tokens')
    op.drop_index('ix_drive_oauth_tokens_id', table_name='drive_oauth_tokens')
    op.drop_table('drive_oauth_tokens')
