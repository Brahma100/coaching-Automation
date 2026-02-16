"""teacher communication settings

Revision ID: 20260214_0028
Revises: 20260213_0027
Create Date: 2026-02-14 21:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260214_0028'
down_revision = '20260213_0027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'teacher_communication_settings' not in tables:
        op.create_table(
            'teacher_communication_settings',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('auth_users.id'), nullable=False),
            sa.Column('provider', sa.String(length=20), nullable=False, server_default='telegram'),
            sa.Column('provider_config_json', sa.Text(), nullable=False, server_default=''),
            sa.Column('enabled_events', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('quiet_hours', sa.Text(), nullable=False, server_default='{"start":"22:00","end":"06:00"}'),
            sa.Column('delete_timer_minutes', sa.Integer(), nullable=False, server_default='15'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('teacher_id', name='uq_teacher_communication_settings_teacher'),
        )
        op.create_index('ix_teacher_communication_settings_id', 'teacher_communication_settings', ['id'])
        op.create_index('ix_teacher_communication_settings_teacher_id', 'teacher_communication_settings', ['teacher_id'])


def downgrade() -> None:
    op.drop_index('ix_teacher_communication_settings_teacher_id', table_name='teacher_communication_settings')
    op.drop_index('ix_teacher_communication_settings_id', table_name='teacher_communication_settings')
    op.drop_table('teacher_communication_settings')

