"""student preferences for automation

Revision ID: 20260210_0016
Revises: 20260210_0015
Create Date: 2026-02-10 00:16:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260210_0016'
down_revision = '20260210_0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {col['name'] for col in inspector.get_columns('students')}

    if 'enable_daily_digest' not in cols:
        op.add_column('students', sa.Column('enable_daily_digest', sa.Boolean(), nullable=False, server_default=sa.text('1')))
        op.create_index('ix_students_enable_daily_digest', 'students', ['enable_daily_digest'])
    if 'enable_homework_reminders' not in cols:
        op.add_column('students', sa.Column('enable_homework_reminders', sa.Boolean(), nullable=False, server_default=sa.text('1')))
        op.create_index('ix_students_enable_homework_reminders', 'students', ['enable_homework_reminders'])
    if 'enable_motivation_messages' not in cols:
        op.add_column('students', sa.Column('enable_motivation_messages', sa.Boolean(), nullable=False, server_default=sa.text('1')))
        op.create_index('ix_students_enable_motivation_messages', 'students', ['enable_motivation_messages'])


def downgrade() -> None:
    op.drop_index('ix_students_enable_motivation_messages', table_name='students')
    op.drop_column('students', 'enable_motivation_messages')
    op.drop_index('ix_students_enable_homework_reminders', table_name='students')
    op.drop_column('students', 'enable_homework_reminders')
    op.drop_index('ix_students_enable_daily_digest', table_name='students')
    op.drop_column('students', 'enable_daily_digest')
