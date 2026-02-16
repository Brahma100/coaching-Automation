"""teacher automation rules

Revision ID: 20260214_0029
Revises: 20260214_0028
Create Date: 2026-02-14 22:05:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260214_0029'
down_revision = '20260214_0028'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'teacher_automation_rules' not in tables:
        op.create_table(
            'teacher_automation_rules',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('auth_users.id'), nullable=False),
            sa.Column('notify_on_attendance', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('class_start_reminder', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('fee_due_alerts', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('student_absence_escalation', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('homework_reminders', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('teacher_id', name='uq_teacher_automation_rules_teacher'),
        )
        op.create_index('ix_teacher_automation_rules_id', 'teacher_automation_rules', ['id'])
        op.create_index('ix_teacher_automation_rules_teacher_id', 'teacher_automation_rules', ['teacher_id'])


def downgrade() -> None:
    op.drop_index('ix_teacher_automation_rules_teacher_id', table_name='teacher_automation_rules')
    op.drop_index('ix_teacher_automation_rules_id', table_name='teacher_automation_rules')
    op.drop_table('teacher_automation_rules')

