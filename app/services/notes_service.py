from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.cache import cache
from app.models import (
    Batch,
    Chapter,
    Note,
    NoteBatch,
    NoteDownloadLog,
    NoteTag,
    NoteVersion,
    Student,
    StudentBatchMap,
    Subject,
    Tag,
    Topic,
)
from app.services.google_drive_service import upload_file


NOTES_CACHE_PREFIX = 'notes_list'
NOTES_ANALYTICS_CACHE_PREFIX = 'notes_analytics'


def invalidate_notes_cache() -> None:
    cache.invalidate_prefix(NOTES_CACHE_PREFIX)
    cache.invalidate_prefix(NOTES_ANALYTICS_CACHE_PREFIX)


def upload_note_pdf(*, file_bytes: bytes, filename: str, mime_type: str, user_id: int) -> dict:
    return upload_file(
        file_stream=file_bytes,
        filename=filename,
        mime_type=mime_type,
        user_id=user_id,
    )


def list_notes_query(
    db: Session,
    *,
    batch_id: int | None = None,
    subject_id: int | None = None,
    topic_id: int | None = None,
    tag: str | None = None,
    search: str | None = None,
    role: str,
    student: Student | None = None,
):
    query = (
        db.query(Note)
        .options(
            joinedload(Note.subject),
            joinedload(Note.chapter),
            joinedload(Note.topic),
            joinedload(Note.batches),
            joinedload(Note.tags),
        )
        .order_by(Note.created_at.desc(), Note.id.desc())
    )

    if batch_id:
        query = query.filter(Note.batches.any(Batch.id == batch_id))

    if subject_id:
        query = query.filter(Note.subject_id == subject_id)

    if topic_id:
        query = query.filter(Note.topic_id == topic_id)

    if tag:
        query = query.filter(Note.tags.any(func.lower(Tag.name) == (tag or '').strip().lower()))

    if search:
        needle = f"%{(search or '').strip().lower()}%"
        query = query.filter(
            func.lower(Note.title).like(needle) | func.lower(Note.description).like(needle)
        )

    now = datetime.utcnow()
    if role == 'student':
        if not student:
            query = query.filter(Note.id == -1)
        else:
            batch_ids = get_student_batch_ids(db, student)
            if batch_ids:
                query = query.filter(Note.batches.any(Batch.id.in_(batch_ids)))
            else:
                query = query.filter(Note.id == -1)

            query = query.filter(
                Note.visible_to_students.is_(True),
                (Note.release_at.is_(None) | (Note.release_at <= now)),
                (Note.expire_at.is_(None) | (Note.expire_at > now)),
            )

    return query


def get_student_batch_ids(db: Session, student: Student) -> list[int]:
    rows = (
        db.query(StudentBatchMap.batch_id)
        .filter(
            StudentBatchMap.student_id == student.id,
            StudentBatchMap.active.is_(True),
        )
        .all()
    )
    batch_ids = [row.batch_id for row in rows]
    if not batch_ids and student.batch_id:
        batch_ids = [student.batch_id]
    return batch_ids


def serialize_note(note: Note) -> dict:
    return {
        'id': note.id,
        'title': note.title,
        'description': note.description,
        'subject_id': note.subject_id,
        'subject': note.subject.name if note.subject else '',
        'chapter_id': note.chapter_id,
        'chapter': note.chapter.name if note.chapter else '',
        'topic_id': note.topic_id,
        'topic': note.topic.name if note.topic else '',
        'drive_file_id': note.drive_file_id,
        'file_size': note.file_size,
        'mime_type': note.mime_type,
        'uploaded_by': note.uploaded_by,
        'visible_to_students': note.visible_to_students,
        'visible_to_parents': note.visible_to_parents,
        'release_at': note.release_at.isoformat() if note.release_at else None,
        'expire_at': note.expire_at.isoformat() if note.expire_at else None,
        'created_at': note.created_at.isoformat() if note.created_at else None,
        'updated_at': note.updated_at.isoformat() if note.updated_at else None,
        'batches': [{'id': batch.id, 'name': batch.name} for batch in (note.batches or [])],
        'tags': [tag.name for tag in (note.tags or [])],
        'version_count': len(note.versions or []),
        'latest_version': (max((version.version_number for version in (note.versions or [])), default=0) or 0),
    }


def ensure_subject_chapter_topic(
    db: Session,
    *,
    subject_id: int,
    chapter_id: int | None,
    topic_id: int | None,
) -> tuple[Subject, Chapter | None, Topic | None]:
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise ValueError('Subject not found')

    chapter = None
    if chapter_id:
        chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            raise ValueError('Chapter not found')
        if chapter.subject_id != subject.id:
            raise ValueError('Chapter does not belong to selected subject')

    topic = None
    if topic_id:
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            raise ValueError('Topic not found')
        if chapter and topic.chapter_id != chapter.id:
            raise ValueError('Topic does not belong to selected chapter')
        if not chapter:
            topic_chapter = db.query(Chapter).filter(Chapter.id == topic.chapter_id).first()
            if topic_chapter and topic_chapter.subject_id != subject.id:
                raise ValueError('Topic does not belong to selected subject')

    return subject, chapter, topic


def sync_note_batches(db: Session, note: Note, batch_ids: Iterable[int]) -> None:
    batch_ids_set = {int(batch_id) for batch_id in batch_ids}
    if not batch_ids_set:
        raise ValueError('At least one batch must be selected')

    batches = db.query(Batch).filter(Batch.id.in_(batch_ids_set)).all()
    found_ids = {batch.id for batch in batches}
    missing = sorted(batch_ids_set.difference(found_ids))
    if missing:
        raise ValueError(f'Invalid batch ids: {", ".join(str(value) for value in missing)}')

    db.query(NoteBatch).filter(NoteBatch.note_id == note.id).delete(synchronize_session=False)
    db.flush()
    for batch in batches:
        db.add(NoteBatch(note_id=note.id, batch_id=batch.id))


def get_or_create_tags(db: Session, names: Iterable[str]) -> list[Tag]:
    cleaned = []
    seen = set()
    for raw in names:
        name = (raw or '').strip()
        if not name:
            continue
        lowered = name.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(name)

    if not cleaned:
        return []

    rows = db.query(Tag).filter(func.lower(Tag.name).in_([name.lower() for name in cleaned])).all()
    existing = {row.name.lower(): row for row in rows}
    result: list[Tag] = []
    for name in cleaned:
        key = name.lower()
        tag = existing.get(key)
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
            existing[key] = tag
        result.append(tag)
    return result


def sync_note_tags(db: Session, note: Note, tag_names: Iterable[str]) -> None:
    tags = get_or_create_tags(db, tag_names)
    db.query(NoteTag).filter(NoteTag.note_id == note.id).delete(synchronize_session=False)
    db.flush()
    for tag in tags:
        db.add(NoteTag(note_id=note.id, tag_id=tag.id))


def create_download_log(
    db: Session,
    *,
    note_id: int,
    student_id: int | None,
    batch_id: int | None,
    ip_address: str,
    user_agent: str,
) -> NoteDownloadLog:
    row = NoteDownloadLog(
        note_id=note_id,
        student_id=student_id,
        batch_id=batch_id,
        ip_address=ip_address,
        user_agent=(user_agent or '')[:255],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_notes_analytics(db: Session, *, role: str, student: Student | None = None) -> dict:
    query = list_notes_query(db, role=role, student=student)
    notes = query.all()

    total_downloads = (
        db.query(func.count(NoteDownloadLog.id)).scalar() if role != 'student' else db.query(func.count(NoteDownloadLog.id))
        .filter(NoteDownloadLog.student_id == (student.id if student else -1))
        .scalar()
    )

    return {
        'total_notes': len(notes),
        'total_subjects': len({note.subject_id for note in notes}),
        'total_tags': len({tag.name for note in notes for tag in note.tags}),
        'total_downloads': int(total_downloads or 0),
    }
