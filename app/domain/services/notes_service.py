from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.core.time_provider import default_time_provider
from app.models import Chapter, Note, NoteVersion, Subject, Topic
from app.services.notes_service import (
    invalidate_notes_cache,
    serialize_note,
    sync_note_batches,
    sync_note_tags,
)


def create_note(
    db: Session,
    *,
    title: str,
    description: str,
    subject: Subject,
    chapter: Chapter | None,
    topic: Topic | None,
    drive_file_id: str,
    file_size: int,
    visible_to_students: bool,
    visible_to_parents: bool,
    release_at: datetime | None,
    expire_at: datetime | None,
    batch_ids: list[int],
    tags: list[str],
    actor_id: int,
    actor_center_id: int,
    note_id: int | None = None,
) -> dict:
    clean_title = (title or '').strip()
    if note_id:
        note = (
            db.query(Note)
            .options(joinedload(Note.versions))
            .filter(Note.id == note_id, Note.center_id == actor_center_id)
            .first()
        )
        if not note:
            raise ValueError('Note not found')
        note.title = clean_title
        note.description = description or ''
        note.subject_id = subject.id
        note.chapter_id = chapter.id if chapter else None
        note.topic_id = topic.id if topic else None
        note.drive_file_id = drive_file_id
        note.file_size = file_size
        note.mime_type = 'application/pdf'
        note.visible_to_students = visible_to_students
        note.visible_to_parents = visible_to_parents
        note.release_at = release_at
        note.expire_at = expire_at
        note.updated_at = default_time_provider.now().replace(tzinfo=None)
        next_version = max((row.version_number for row in note.versions), default=0) + 1
    else:
        note = Note(
            title=clean_title,
            description=description or '',
            subject_id=subject.id,
            chapter_id=chapter.id if chapter else None,
            topic_id=topic.id if topic else None,
            drive_file_id=drive_file_id,
            file_size=file_size,
            mime_type='application/pdf',
            uploaded_by=actor_id,
            center_id=actor_center_id,
            visible_to_students=visible_to_students,
            visible_to_parents=visible_to_parents,
            release_at=release_at,
            expire_at=expire_at,
        )
        db.add(note)
        db.flush()
        next_version = 1

    sync_note_batches(db, note, batch_ids)
    sync_note_tags(db, note, tags)

    db.add(
        NoteVersion(
            note_id=note.id,
            version_number=next_version,
            drive_file_id=drive_file_id,
            file_size=file_size,
            mime_type='application/pdf',
            uploaded_by=actor_id,
        )
    )
    db.commit()
    db.refresh(note)
    invalidate_notes_cache()

    result = (
        db.query(Note)
        .options(joinedload(Note.batches), joinedload(Note.tags), joinedload(Note.versions), joinedload(Note.subject), joinedload(Note.chapter), joinedload(Note.topic))
        .filter(Note.id == note.id, Note.center_id == actor_center_id)
        .first()
    )
    return {
        'ok': True,
        'note': serialize_note(result),
    }
