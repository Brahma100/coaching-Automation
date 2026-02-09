"""automation entities: class sessions, parents, action tokens, offers

Revision ID: 20260209_0002
Revises: 20260209_0001
Create Date: 2026-02-09 00:02:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260209_0002'
down_revision = '20260209_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'class_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('batches.id'), nullable=False),
        sa.Column('subject', sa.String(length=80), nullable=False, server_default='General'),
        sa.Column('scheduled_start', sa.DateTime(), nullable=False),
        sa.Column('actual_start', sa.DateTime(), nullable=True),
        sa.Column('topic_planned', sa.Text(), nullable=False, server_default=''),
        sa.Column('topic_completed', sa.Text(), nullable=False, server_default=''),
        sa.Column('teacher_id', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='scheduled'),
    )
    op.create_index('ix_class_sessions_id', 'class_sessions', ['id'])
    op.create_index('ix_class_sessions_batch_id', 'class_sessions', ['batch_id'])
    op.create_index('ix_class_sessions_scheduled_start', 'class_sessions', ['scheduled_start'])
    op.create_index('ix_class_sessions_teacher_id', 'class_sessions', ['teacher_id'])

    op.create_table(
        'parents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False, server_default=''),
        sa.Column('telegram_chat_id', sa.String(length=40), nullable=False, server_default=''),
    )
    op.create_index('ix_parents_id', 'parents', ['id'])

    op.create_table(
        'parent_student_map',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('parents.id'), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('relation', sa.String(length=30), nullable=False, server_default='guardian'),
    )
    op.create_index('ix_parent_student_map_id', 'parent_student_map', ['id'])
    op.create_index('ix_parent_student_map_parent_id', 'parent_student_map', ['parent_id'])
    op.create_index('ix_parent_student_map_student_id', 'parent_student_map', ['student_id'])

    op.create_table(
        'action_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('action_type', sa.String(length=40), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('consumed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_action_tokens_id', 'action_tokens', ['id'])
    op.create_index('ix_action_tokens_token_hash', 'action_tokens', ['token_hash'], unique=True)
    op.create_index('ix_action_tokens_action_type', 'action_tokens', ['action_type'])
    op.create_index('ix_action_tokens_expires_at', 'action_tokens', ['expires_at'])
    op.create_index('ix_action_tokens_consumed', 'action_tokens', ['consumed'])

    op.create_table(
        'offers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=40), nullable=False),
        sa.Column('title', sa.String(length=140), nullable=False),
        sa.Column('discount_type', sa.String(length=20), nullable=False, server_default='flat'),
        sa.Column('discount_value', sa.Float(), nullable=False, server_default='0'),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_to', sa.Date(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index('ix_offers_id', 'offers', ['id'])
    op.create_index('ix_offers_code', 'offers', ['code'], unique=True)

    op.create_table(
        'offer_redemptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('offer_id', sa.Integer(), sa.ForeignKey('offers.id'), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('fee_record_id', sa.Integer(), nullable=True),
        sa.Column('referral_code_id', sa.Integer(), nullable=True),
        sa.Column('discount_amount', sa.Float(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_offer_redemptions_id', 'offer_redemptions', ['id'])


def downgrade() -> None:
    op.drop_index('ix_offer_redemptions_id', table_name='offer_redemptions')
    op.drop_table('offer_redemptions')

    op.drop_index('ix_offers_code', table_name='offers')
    op.drop_index('ix_offers_id', table_name='offers')
    op.drop_table('offers')

    op.drop_index('ix_action_tokens_consumed', table_name='action_tokens')
    op.drop_index('ix_action_tokens_expires_at', table_name='action_tokens')
    op.drop_index('ix_action_tokens_action_type', table_name='action_tokens')
    op.drop_index('ix_action_tokens_token_hash', table_name='action_tokens')
    op.drop_index('ix_action_tokens_id', table_name='action_tokens')
    op.drop_table('action_tokens')

    op.drop_index('ix_parent_student_map_student_id', table_name='parent_student_map')
    op.drop_index('ix_parent_student_map_parent_id', table_name='parent_student_map')
    op.drop_index('ix_parent_student_map_id', table_name='parent_student_map')
    op.drop_table('parent_student_map')

    op.drop_index('ix_parents_id', table_name='parents')
    op.drop_table('parents')

    op.drop_index('ix_class_sessions_teacher_id', table_name='class_sessions')
    op.drop_index('ix_class_sessions_scheduled_start', table_name='class_sessions')
    op.drop_index('ix_class_sessions_batch_id', table_name='class_sessions')
    op.drop_index('ix_class_sessions_id', table_name='class_sessions')
    op.drop_table('class_sessions')
