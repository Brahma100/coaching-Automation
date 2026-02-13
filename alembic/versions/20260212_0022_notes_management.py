"""add notes management schema

Revision ID: 20260212_0022
Revises: 20260211_0021
Create Date: 2026-02-12
"""

from alembic import op
import sqlalchemy as sa


revision = '20260212_0022'
down_revision = '20260211_0021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'chapters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subject_id', 'name', name='uq_chapter_subject_name'),
    )
    op.create_index('ix_chapters_id', 'chapters', ['id'])
    op.create_index('ix_chapters_name', 'chapters', ['name'])
    op.create_index('ix_chapters_subject_id', 'chapters', ['subject_id'])
    op.create_index('ix_chapters_created_at', 'chapters', ['created_at'])
    op.create_index('ix_chapters_subject_name', 'chapters', ['subject_id', 'name'])

    op.create_table(
        'topics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chapter_id', sa.Integer(), nullable=False),
        sa.Column('parent_topic_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id']),
        sa.ForeignKeyConstraint(['parent_topic_id'], ['topics.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_topics_id', 'topics', ['id'])
    op.create_index('ix_topics_chapter_id', 'topics', ['chapter_id'])
    op.create_index('ix_topics_parent_topic_id', 'topics', ['parent_topic_id'])
    op.create_index('ix_topics_name', 'topics', ['name'])
    op.create_index('ix_topics_created_at', 'topics', ['created_at'])
    op.create_index('ix_topics_chapter_parent_name', 'topics', ['chapter_id', 'parent_topic_id', 'name'])

    op.create_table(
        'notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('chapter_id', sa.Integer(), nullable=True),
        sa.Column('topic_id', sa.Integer(), nullable=True),
        sa.Column('drive_file_id', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(length=120), nullable=False),
        sa.Column('uploaded_by', sa.Integer(), nullable=False),
        sa.Column('visible_to_students', sa.Boolean(), nullable=False),
        sa.Column('visible_to_parents', sa.Boolean(), nullable=False),
        sa.Column('release_at', sa.DateTime(), nullable=True),
        sa.Column('expire_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id']),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id']),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notes_id', 'notes', ['id'])
    op.create_index('ix_notes_title', 'notes', ['title'])
    op.create_index('ix_notes_subject_id', 'notes', ['subject_id'])
    op.create_index('ix_notes_chapter_id', 'notes', ['chapter_id'])
    op.create_index('ix_notes_topic_id', 'notes', ['topic_id'])
    op.create_index('ix_notes_drive_file_id', 'notes', ['drive_file_id'])
    op.create_index('ix_notes_uploaded_by', 'notes', ['uploaded_by'])
    op.create_index('ix_notes_visible_to_students', 'notes', ['visible_to_students'])
    op.create_index('ix_notes_visible_to_parents', 'notes', ['visible_to_parents'])
    op.create_index('ix_notes_release_at', 'notes', ['release_at'])
    op.create_index('ix_notes_expire_at', 'notes', ['expire_at'])
    op.create_index('ix_notes_created_at', 'notes', ['created_at'])
    op.create_index('ix_notes_updated_at', 'notes', ['updated_at'])
    op.create_index('ix_notes_subject_topic_created', 'notes', ['subject_id', 'topic_id', 'created_at'])
    op.create_index('ix_notes_release_expire', 'notes', ['release_at', 'expire_at'])

    op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_tags_id', 'tags', ['id'])
    op.create_index('ix_tags_name', 'tags', ['name'])
    op.create_index('ix_tags_created_at', 'tags', ['created_at'])

    op.create_table(
        'note_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('note_id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['batch_id'], ['batches.id']),
        sa.ForeignKeyConstraint(['note_id'], ['notes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('note_id', 'batch_id', name='uq_note_batch_note_batch'),
    )
    op.create_index('ix_note_batches_id', 'note_batches', ['id'])
    op.create_index('ix_note_batches_note_id', 'note_batches', ['note_id'])
    op.create_index('ix_note_batches_batch_id', 'note_batches', ['batch_id'])

    op.create_table(
        'note_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('note_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['note_id'], ['notes.id']),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('note_id', 'tag_id', name='uq_note_tag_note_tag'),
    )
    op.create_index('ix_note_tags_id', 'note_tags', ['id'])
    op.create_index('ix_note_tags_note_id', 'note_tags', ['note_id'])
    op.create_index('ix_note_tags_tag_id', 'note_tags', ['tag_id'])

    op.create_table(
        'note_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('note_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('drive_file_id', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(length=120), nullable=False),
        sa.Column('uploaded_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['note_id'], ['notes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('note_id', 'version_number', name='uq_note_version_note_number'),
    )
    op.create_index('ix_note_versions_id', 'note_versions', ['id'])
    op.create_index('ix_note_versions_note_id', 'note_versions', ['note_id'])
    op.create_index('ix_note_versions_version_number', 'note_versions', ['version_number'])
    op.create_index('ix_note_versions_drive_file_id', 'note_versions', ['drive_file_id'])
    op.create_index('ix_note_versions_uploaded_by', 'note_versions', ['uploaded_by'])
    op.create_index('ix_note_versions_created_at', 'note_versions', ['created_at'])

    op.create_table(
        'note_download_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('note_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=True),
        sa.Column('batch_id', sa.Integer(), nullable=True),
        sa.Column('downloaded_at', sa.DateTime(), nullable=False),
        sa.Column('ip_address', sa.String(length=64), nullable=False),
        sa.Column('user_agent', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['batch_id'], ['batches.id']),
        sa.ForeignKeyConstraint(['note_id'], ['notes.id']),
        sa.ForeignKeyConstraint(['student_id'], ['students.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_note_download_logs_id', 'note_download_logs', ['id'])
    op.create_index('ix_note_download_logs_note_id', 'note_download_logs', ['note_id'])
    op.create_index('ix_note_download_logs_student_id', 'note_download_logs', ['student_id'])
    op.create_index('ix_note_download_logs_batch_id', 'note_download_logs', ['batch_id'])
    op.create_index('ix_note_download_logs_downloaded_at', 'note_download_logs', ['downloaded_at'])
    op.create_index('ix_note_download_logs_note_student', 'note_download_logs', ['note_id', 'student_id'])


def downgrade() -> None:
    op.drop_index('ix_note_download_logs_note_student', table_name='note_download_logs')
    op.drop_index('ix_note_download_logs_downloaded_at', table_name='note_download_logs')
    op.drop_index('ix_note_download_logs_batch_id', table_name='note_download_logs')
    op.drop_index('ix_note_download_logs_student_id', table_name='note_download_logs')
    op.drop_index('ix_note_download_logs_note_id', table_name='note_download_logs')
    op.drop_index('ix_note_download_logs_id', table_name='note_download_logs')
    op.drop_table('note_download_logs')

    op.drop_index('ix_note_versions_created_at', table_name='note_versions')
    op.drop_index('ix_note_versions_uploaded_by', table_name='note_versions')
    op.drop_index('ix_note_versions_drive_file_id', table_name='note_versions')
    op.drop_index('ix_note_versions_version_number', table_name='note_versions')
    op.drop_index('ix_note_versions_note_id', table_name='note_versions')
    op.drop_index('ix_note_versions_id', table_name='note_versions')
    op.drop_table('note_versions')

    op.drop_index('ix_note_tags_tag_id', table_name='note_tags')
    op.drop_index('ix_note_tags_note_id', table_name='note_tags')
    op.drop_index('ix_note_tags_id', table_name='note_tags')
    op.drop_table('note_tags')

    op.drop_index('ix_note_batches_batch_id', table_name='note_batches')
    op.drop_index('ix_note_batches_note_id', table_name='note_batches')
    op.drop_index('ix_note_batches_id', table_name='note_batches')
    op.drop_table('note_batches')

    op.drop_index('ix_tags_created_at', table_name='tags')
    op.drop_index('ix_tags_name', table_name='tags')
    op.drop_index('ix_tags_id', table_name='tags')
    op.drop_table('tags')

    op.drop_index('ix_notes_release_expire', table_name='notes')
    op.drop_index('ix_notes_subject_topic_created', table_name='notes')
    op.drop_index('ix_notes_updated_at', table_name='notes')
    op.drop_index('ix_notes_created_at', table_name='notes')
    op.drop_index('ix_notes_expire_at', table_name='notes')
    op.drop_index('ix_notes_release_at', table_name='notes')
    op.drop_index('ix_notes_visible_to_parents', table_name='notes')
    op.drop_index('ix_notes_visible_to_students', table_name='notes')
    op.drop_index('ix_notes_uploaded_by', table_name='notes')
    op.drop_index('ix_notes_drive_file_id', table_name='notes')
    op.drop_index('ix_notes_topic_id', table_name='notes')
    op.drop_index('ix_notes_chapter_id', table_name='notes')
    op.drop_index('ix_notes_subject_id', table_name='notes')
    op.drop_index('ix_notes_title', table_name='notes')
    op.drop_index('ix_notes_id', table_name='notes')
    op.drop_table('notes')

    op.drop_index('ix_topics_chapter_parent_name', table_name='topics')
    op.drop_index('ix_topics_created_at', table_name='topics')
    op.drop_index('ix_topics_name', table_name='topics')
    op.drop_index('ix_topics_parent_topic_id', table_name='topics')
    op.drop_index('ix_topics_chapter_id', table_name='topics')
    op.drop_index('ix_topics_id', table_name='topics')
    op.drop_table('topics')

    op.drop_index('ix_chapters_subject_name', table_name='chapters')
    op.drop_index('ix_chapters_created_at', table_name='chapters')
    op.drop_index('ix_chapters_subject_id', table_name='chapters')
    op.drop_index('ix_chapters_name', table_name='chapters')
    op.drop_index('ix_chapters_id', table_name='chapters')
    op.drop_table('chapters')
