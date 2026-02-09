"""add student risk engine tables

Revision ID: 20260209_0006
Revises: 20260209_0005
Create Date: 2026-02-09 00:06:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '20260209_0006'
down_revision = '20260209_0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if 'student_risk_profiles' not in tables:
        op.create_table(
            'student_risk_profiles',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
            sa.Column('attendance_score', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('homework_score', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('fee_score', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('test_score', sa.Float(), nullable=True),
            sa.Column('final_risk_score', sa.Float(), nullable=False, server_default='100.0'),
            sa.Column('risk_level', sa.String(length=10), nullable=False, server_default='LOW'),
            sa.Column('last_computed_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )

    profile_indexes = {idx['name'] for idx in inspector.get_indexes('student_risk_profiles')}
    if 'ix_student_risk_profiles_id' not in profile_indexes:
        op.create_index('ix_student_risk_profiles_id', 'student_risk_profiles', ['id'])
    if 'ix_student_risk_profiles_student_id' not in profile_indexes:
        op.create_index('ix_student_risk_profiles_student_id', 'student_risk_profiles', ['student_id'], unique=True)
    if 'ix_student_risk_profiles_final_risk_score' not in profile_indexes:
        op.create_index('ix_student_risk_profiles_final_risk_score', 'student_risk_profiles', ['final_risk_score'])
    if 'ix_student_risk_profiles_risk_level' not in profile_indexes:
        op.create_index('ix_student_risk_profiles_risk_level', 'student_risk_profiles', ['risk_level'])
    if 'ix_student_risk_profiles_last_computed_at' not in profile_indexes:
        op.create_index('ix_student_risk_profiles_last_computed_at', 'student_risk_profiles', ['last_computed_at'])

    if 'student_risk_events' not in tables:
        op.create_table(
            'student_risk_events',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
            sa.Column('previous_risk_level', sa.String(length=10), nullable=True),
            sa.Column('new_risk_level', sa.String(length=10), nullable=False),
            sa.Column('reason_json', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        )

    event_indexes = {idx['name'] for idx in inspector.get_indexes('student_risk_events')}
    if 'ix_student_risk_events_id' not in event_indexes:
        op.create_index('ix_student_risk_events_id', 'student_risk_events', ['id'])
    if 'ix_student_risk_events_student_id' not in event_indexes:
        op.create_index('ix_student_risk_events_student_id', 'student_risk_events', ['student_id'])
    if 'ix_student_risk_events_new_risk_level' not in event_indexes:
        op.create_index('ix_student_risk_events_new_risk_level', 'student_risk_events', ['new_risk_level'])
    if 'ix_student_risk_events_created_at' not in event_indexes:
        op.create_index('ix_student_risk_events_created_at', 'student_risk_events', ['created_at'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if 'student_risk_events' in tables:
        event_indexes = {idx['name'] for idx in inspector.get_indexes('student_risk_events')}
        if 'ix_student_risk_events_created_at' in event_indexes:
            op.drop_index('ix_student_risk_events_created_at', table_name='student_risk_events')
        if 'ix_student_risk_events_new_risk_level' in event_indexes:
            op.drop_index('ix_student_risk_events_new_risk_level', table_name='student_risk_events')
        if 'ix_student_risk_events_student_id' in event_indexes:
            op.drop_index('ix_student_risk_events_student_id', table_name='student_risk_events')
        if 'ix_student_risk_events_id' in event_indexes:
            op.drop_index('ix_student_risk_events_id', table_name='student_risk_events')
        op.drop_table('student_risk_events')

    if 'student_risk_profiles' in tables:
        profile_indexes = {idx['name'] for idx in inspector.get_indexes('student_risk_profiles')}
        if 'ix_student_risk_profiles_last_computed_at' in profile_indexes:
            op.drop_index('ix_student_risk_profiles_last_computed_at', table_name='student_risk_profiles')
        if 'ix_student_risk_profiles_risk_level' in profile_indexes:
            op.drop_index('ix_student_risk_profiles_risk_level', table_name='student_risk_profiles')
        if 'ix_student_risk_profiles_final_risk_score' in profile_indexes:
            op.drop_index('ix_student_risk_profiles_final_risk_score', table_name='student_risk_profiles')
        if 'ix_student_risk_profiles_student_id' in profile_indexes:
            op.drop_index('ix_student_risk_profiles_student_id', table_name='student_risk_profiles')
        if 'ix_student_risk_profiles_id' in profile_indexes:
            op.drop_index('ix_student_risk_profiles_id', table_name='student_risk_profiles')
        op.drop_table('student_risk_profiles')
