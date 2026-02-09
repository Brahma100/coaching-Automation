"""initial core tables

Revision ID: 20260209_0001
Revises: 
Create Date: 2026-02-09 00:01:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260209_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'batches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False, unique=True),
        sa.Column('start_time', sa.String(length=10), nullable=False, server_default='07:00'),
    )
    op.create_index('ix_batches_id', 'batches', ['id'])

    op.create_table(
        'students',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('guardian_phone', sa.String(length=20), nullable=False, server_default=''),
        sa.Column('telegram_chat_id', sa.String(length=40), nullable=False, server_default=''),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('batches.id'), nullable=False),
    )
    op.create_index('ix_students_id', 'students', ['id'])

    op.create_table(
        'attendance_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('attendance_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False, server_default=''),
        sa.Column('marked_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_attendance_records_id', 'attendance_records', ['id'])

    op.create_table(
        'fee_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('paid_amount', sa.Float(), nullable=False, server_default='0'),
        sa.Column('is_paid', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('upi_link', sa.String(length=255), nullable=False, server_default=''),
    )
    op.create_index('ix_fee_records_id', 'fee_records', ['id'])

    op.create_table(
        'homework',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('attachment_path', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_homework_id', 'homework', ['id'])

    op.create_table(
        'homework_submissions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('homework_id', sa.Integer(), sa.ForeignKey('homework.id'), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('file_path', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_homework_submissions_id', 'homework_submissions', ['id'])

    op.create_table(
        'referral_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('code', sa.String(length=24), nullable=False),
        sa.Column('reward_points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_referral_codes_id', 'referral_codes', ['id'])
    op.create_index('ix_referral_codes_code', 'referral_codes', ['code'], unique=True)

    op.create_table(
        'communication_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), nullable=True),
        sa.Column('channel', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='queued'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_communication_logs_id', 'communication_logs', ['id'])


def downgrade() -> None:
    op.drop_index('ix_communication_logs_id', table_name='communication_logs')
    op.drop_table('communication_logs')

    op.drop_index('ix_referral_codes_code', table_name='referral_codes')
    op.drop_index('ix_referral_codes_id', table_name='referral_codes')
    op.drop_table('referral_codes')

    op.drop_index('ix_homework_submissions_id', table_name='homework_submissions')
    op.drop_table('homework_submissions')

    op.drop_index('ix_homework_id', table_name='homework')
    op.drop_table('homework')

    op.drop_index('ix_fee_records_id', table_name='fee_records')
    op.drop_table('fee_records')

    op.drop_index('ix_attendance_records_id', table_name='attendance_records')
    op.drop_table('attendance_records')

    op.drop_index('ix_students_id', table_name='students')
    op.drop_table('students')

    op.drop_index('ix_batches_id', table_name='batches')
    op.drop_table('batches')
