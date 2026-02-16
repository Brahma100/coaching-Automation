from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.cache import cache, cache_key
from app.domain.services.notes_service import create_note as domain_create_note
from app.core.time_provider import default_time_provider
from app.db import get_db
from app.models import Batch, Chapter, Note, NoteVersion, Role, Subject, Tag, Topic
from app.services.auth_service import validate_session_token
from app.services.drive_oauth_service import DriveNotConnectedError
from app.services.google_drive_service import DriveStorageError, delete_file, stream_file
from app.services.notes_service import (
    NOTES_ANALYTICS_CACHE_PREFIX,
    NOTES_CACHE_PREFIX,
    get_student_batch_ids,
    invalidate_notes_cache,
    list_notes_analytics,
    list_notes_query,
    serialize_note,
    sync_note_batches,
    sync_note_tags,
    upload_note_pdf,
)
from app.services.student_portal_service import require_student_session


router = APIRouter(prefix='/api/notes', tags=['Notes'])
logger = logging.getLogger(__name__)


def _resolve_token(request: Request) -> str | None:
    token = request.cookies.get('auth_session')
    if token:
        return token
    authorization = request.headers.get('authorization', '')
    if authorization.lower().startswith('bearer '):
        return authorization[7:].strip()
    return None


def _require_session(request: Request) -> dict:
    token = _resolve_token(request)
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    role = (session.get('role') or '').lower()
    if role not in (Role.TEACHER.value, Role.ADMIN.value, Role.STUDENT.value):
        raise HTTPException(status_code=403, detail='Unauthorized')
    return session


def _require_teacher(request: Request) -> dict:
    session = _require_session(request)
    role = (session.get('role') or '').lower()
    if role not in (Role.TEACHER.value, Role.ADMIN.value):
        raise HTTPException(status_code=403, detail='Teacher access required')
    return session


def _parse_multi_values(raw: str | None) -> list[str]:
    if raw is None:
        return []
    value = (raw or '').strip()
    if not value:
        return []
    if value.startswith('['):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            pass
    return [chunk.strip() for chunk in value.split(',') if chunk.strip()]


def _parse_datetime(value: str | None) -> datetime | None:
    raw = (value or '').strip()
    if not raw:
        return None
    if raw.endswith('Z'):
        raw = raw[:-1] + '+00:00'
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='Invalid datetime format, expected ISO-8601') from exc
    if parsed.tzinfo:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed


def _is_pdf(file_name: str, content_type: str, file_bytes: bytes) -> bool:
    normalized_name = (file_name or '').lower()
    normalized_type = (content_type or '').lower()
    return (
        normalized_name.endswith('.pdf')
        and (normalized_type in ('application/pdf', 'application/octet-stream', '') or 'pdf' in normalized_type)
        and file_bytes.startswith(b'%PDF')
    )


def _resolve_subject(db: Session, subject_id: int | None, subject_name: str | None) -> Subject:
    if subject_id:
        row = db.query(Subject).filter(Subject.id == subject_id).first()
        if not row:
            raise HTTPException(status_code=400, detail='Subject not found')
        return row

    clean_name = (subject_name or '').strip()
    if clean_name:
        row = db.query(Subject).filter(func.lower(Subject.name) == clean_name.lower()).first()
        if row:
            return row
        row = Subject(name=clean_name, code='')
        db.add(row)
        db.flush()
        return row

    fallback_name = 'General'
    row = db.query(Subject).filter(func.lower(Subject.name) == fallback_name.lower()).first()
    if row:
        return row
    row = Subject(name=fallback_name, code='GEN')
    db.add(row)
    db.flush()
    return row


def _resolve_chapter(
    db: Session,
    subject: Subject,
    chapter_id: int | None,
    chapter_name: str | None,
) -> Chapter | None:
    if chapter_id:
        row = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not row:
            raise HTTPException(status_code=400, detail='Chapter not found')
        if row.subject_id != subject.id:
            raise HTTPException(status_code=400, detail='Chapter does not belong to selected subject')
        return row

    clean_name = (chapter_name or '').strip()
    if not clean_name:
        return None
    row = db.query(Chapter).filter(
        Chapter.subject_id == subject.id,
        func.lower(Chapter.name) == clean_name.lower(),
    ).first()
    if row:
        return row
    row = Chapter(subject_id=subject.id, name=clean_name)
    db.add(row)
    db.flush()
    return row


def _resolve_topic(
    db: Session,
    subject: Subject,
    chapter: Chapter | None,
    topic_id: int | None,
    topic_name: str | None,
) -> Topic | None:
    if topic_id:
        row = db.query(Topic).filter(Topic.id == topic_id).first()
        if not row:
            raise HTTPException(status_code=400, detail='Topic not found')
        row_chapter = db.query(Chapter).filter(Chapter.id == row.chapter_id).first()
        if chapter and row.chapter_id != chapter.id:
            raise HTTPException(status_code=400, detail='Topic does not belong to selected chapter')
        if not chapter and row_chapter and row_chapter.subject_id != subject.id:
            raise HTTPException(status_code=400, detail='Topic does not belong to selected subject')
        return row

    clean_name = (topic_name or '').strip()
    if not clean_name:
        return None
    effective_chapter = chapter
    if not effective_chapter:
        effective_chapter = db.query(Chapter).filter(
            Chapter.subject_id == subject.id,
            func.lower(Chapter.name) == 'general',
        ).first()
        if not effective_chapter:
            effective_chapter = Chapter(subject_id=subject.id, name='General')
            db.add(effective_chapter)
            db.flush()

    row = db.query(Topic).filter(
        Topic.chapter_id == effective_chapter.id,
        func.lower(Topic.name) == clean_name.lower(),
    ).first()
    if row:
        return row
    row = Topic(chapter_id=effective_chapter.id, name=clean_name)
    db.add(row)
    db.flush()
    return row


@router.get('/metadata')
def notes_metadata(
    request: Request,
    db: Session = Depends(get_db),
):
    session = _require_session(request)
    role = (session.get('role') or '').lower()

    subjects = db.query(Subject).options(joinedload(Subject.chapters)).order_by(Subject.name.asc()).all()
    chapters = db.query(Chapter).order_by(Chapter.name.asc()).all()
    topics = db.query(Topic).order_by(Topic.name.asc()).all()
    tags = db.query(Tag).order_by(Tag.name.asc()).all()

    if role == Role.STUDENT.value:
        auth = require_student_session(db, _resolve_token(request))
        student = auth['student']
        batch_ids = get_student_batch_ids(db, student, center_id=int(session.get('center_id') or 0))
        batches = db.query(Batch).filter(Batch.id.in_(batch_ids)).order_by(Batch.name.asc()).all() if batch_ids else []
    else:
        batches = db.query(Batch).filter(Batch.active.is_(True), Batch.center_id == int(session.get('center_id') or 0)).order_by(Batch.name.asc()).all()

    return {
        'subjects': [{'id': row.id, 'name': row.name} for row in subjects],
        'chapters': [{'id': row.id, 'subject_id': row.subject_id, 'name': row.name} for row in chapters],
        'topics': [
            {
                'id': row.id,
                'chapter_id': row.chapter_id,
                'parent_topic_id': row.parent_topic_id,
                'name': row.name,
            }
            for row in topics
        ],
        'tags': [{'id': row.id, 'name': row.name} for row in tags],
        'batches': [{'id': row.id, 'name': row.name} for row in batches],
    }


@router.get('/analytics')
def notes_analytics(
    request: Request,
    bypass_cache: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    session = _require_session(request)
    role = (session.get('role') or '').lower()
    student = None
    if role == Role.STUDENT.value:
        student = require_student_session(db, _resolve_token(request))['student']

    key = cache_key(
        NOTES_ANALYTICS_CACHE_PREFIX,
        f"{role}:{int(session.get('user_id') or 0)}:{int(student.id if student else 0)}",
    )
    if not bypass_cache:
        cached = cache.get_cached(key)
        if cached is not None:
            return cached

    payload = list_notes_analytics(db, center_id=int(session.get('center_id') or 0), role=role, student=student)
    cache.set_cached(key, payload, ttl=60)
    return payload


@router.get('')
def list_notes(
    request: Request,
    batch_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    topic_id: int | None = Query(default=None),
    tag: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    bypass_cache: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    session = _require_session(request)
    role = (session.get('role') or '').lower()
    student = None
    if role == Role.STUDENT.value:
        student = require_student_session(db, _resolve_token(request))['student']

    cache_suffix = '|'.join(
        [
            role,
            str(int(session.get('user_id') or 0)),
            str(int(student.id if student else 0)),
            str(batch_id or 0),
            str(subject_id or 0),
            str(topic_id or 0),
            (tag or '').strip().lower(),
            (search or '').strip().lower(),
            str(page),
            str(page_size),
        ]
    )
    key = cache_key(NOTES_CACHE_PREFIX, cache_suffix)
    if not bypass_cache:
        cached = cache.get_cached(key)
        if cached is not None:
            return cached

    query = list_notes_query(
        db,
        center_id=int(session.get('center_id') or 0),
        batch_id=batch_id,
        subject_id=subject_id,
        topic_id=topic_id,
        tag=tag,
        search=search,
        role=role,
        student=student,
    )

    total = query.count()
    offset = (page - 1) * page_size
    rows = (
        query.options(joinedload(Note.versions))
        .offset(offset)
        .limit(page_size)
        .all()
    )

    payload = {
        'items': [serialize_note(row) for row in rows],
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': max(1, (total + page_size - 1) // page_size),
        },
    }
    cache.set_cached(key, payload, ttl=60)
    return payload


@router.post('/upload')
async def upload_note(
    request: Request,
    title: str = Form(...),
    description: str = Form(default=''),
    subject_id: int | None = Form(default=None),
    subject_name: str = Form(default=''),
    chapter_id: int | None = Form(default=None),
    chapter_name: str = Form(default=''),
    topic_id: int | None = Form(default=None),
    topic_name: str = Form(default=''),
    batch_ids: str = Form(default=''),
    tags: str = Form(default=''),
    visible_to_students: bool = Form(default=True),
    visible_to_parents: bool = Form(default=False),
    release_at: str | None = Form(default=None),
    expire_at: str | None = Form(default=None),
    note_id: int | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    session = _require_teacher(request)

    clean_title = (title or '').strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail='Title is required')

    release_at_dt = _parse_datetime(release_at)
    expire_at_dt = _parse_datetime(expire_at)
    if release_at_dt and expire_at_dt and release_at_dt >= expire_at_dt:
        raise HTTPException(status_code=400, detail='release_at must be earlier than expire_at')

    file_bytes = await file.read()
    if not _is_pdf(file.filename or '', file.content_type or '', file_bytes):
        raise HTTPException(status_code=400, detail='Only valid PDF files are allowed')

    try:
        drive_payload = upload_note_pdf(
            file_bytes=file_bytes,
            filename=file.filename or f'{clean_title}.pdf',
            mime_type='application/pdf',
            user_id=int(session.get('user_id') or 0),
        )
        drive_file_id = drive_payload['file_id']
    except DriveNotConnectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DriveStorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        subject = _resolve_subject(db, subject_id, subject_name)
        chapter = _resolve_chapter(db, subject, chapter_id, chapter_name)
        topic = _resolve_topic(db, subject, chapter, topic_id, topic_name)

        parsed_batch_ids = [int(value) for value in _parse_multi_values(batch_ids)]
        parsed_tags = _parse_multi_values(tags)

        actor_id = int(session.get('user_id') or 0)
        actor_center_id = int(session.get('center_id') or 1)
        return domain_create_note(
            db,
            title=clean_title,
            description=description or '',
            subject=subject,
            chapter=chapter,
            topic=topic,
            drive_file_id=drive_file_id,
            file_size=len(file_bytes),
            visible_to_students=visible_to_students,
            visible_to_parents=visible_to_parents,
            release_at=release_at_dt,
            expire_at=expire_at_dt,
            batch_ids=parsed_batch_ids,
            tags=parsed_tags,
            actor_id=actor_id,
            actor_center_id=actor_center_id,
            note_id=note_id,
        )
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        detail = str(exc)
        if detail == 'Note not found':
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc


@router.put('/{note_id}')
async def update_note(
    note_id: int,
    request: Request,
    title: str = Form(...),
    description: str = Form(default=''),
    subject_id: int | None = Form(default=None),
    subject_name: str = Form(default=''),
    chapter_id: int | None = Form(default=None),
    chapter_name: str = Form(default=''),
    topic_id: int | None = Form(default=None),
    topic_name: str = Form(default=''),
    batch_ids: str = Form(default=''),
    tags: str = Form(default=''),
    visible_to_students: bool = Form(default=True),
    visible_to_parents: bool = Form(default=False),
    release_at: str | None = Form(default=None),
    expire_at: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
):
    session = _require_teacher(request)

    clean_title = (title or '').strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail='Title is required')

    note = (
        db.query(Note)
        .options(joinedload(Note.versions))
        .filter(Note.id == note_id, Note.center_id == int(session.get('center_id') or 0))
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail='Note not found')

    release_at_dt = _parse_datetime(release_at)
    expire_at_dt = _parse_datetime(expire_at)
    if release_at_dt and expire_at_dt and release_at_dt >= expire_at_dt:
        raise HTTPException(status_code=400, detail='release_at must be earlier than expire_at')

    has_new_file = file is not None and bool(file.filename)
    file_bytes: bytes | None = None
    new_drive_file_id: str | None = None
    new_file_size: int | None = None
    old_drive_file_id: str | None = None
    if has_new_file and file is not None:
        file_bytes = await file.read()
        if not _is_pdf(file.filename or '', file.content_type or '', file_bytes):
            raise HTTPException(status_code=400, detail='Only valid PDF files are allowed')
        try:
            drive_payload = upload_note_pdf(
                file_bytes=file_bytes,
                filename=file.filename or f'{clean_title}.pdf',
                mime_type='application/pdf',
                user_id=int(session.get('user_id') or 0),
            )
            new_drive_file_id = drive_payload['file_id']
            new_file_size = len(file_bytes)
            old_drive_file_id = note.drive_file_id
        except DriveNotConnectedError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except DriveStorageError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        subject = _resolve_subject(db, subject_id, subject_name)
        chapter = _resolve_chapter(db, subject, chapter_id, chapter_name)
        topic = _resolve_topic(db, subject, chapter, topic_id, topic_name)

        parsed_batch_ids = [int(value) for value in _parse_multi_values(batch_ids)]
        parsed_tags = _parse_multi_values(tags)

        note.title = clean_title
        note.description = description or ''
        note.subject_id = subject.id
        note.chapter_id = chapter.id if chapter else None
        note.topic_id = topic.id if topic else None
        note.visible_to_students = visible_to_students
        note.visible_to_parents = visible_to_parents
        note.release_at = release_at_dt
        note.expire_at = expire_at_dt
        note.updated_at = default_time_provider.now().replace(tzinfo=None)

        actor_id = int(session.get('user_id') or 0)
        if has_new_file and new_drive_file_id and new_file_size is not None:
            note.drive_file_id = new_drive_file_id
            note.file_size = int(new_file_size)
            note.mime_type = 'application/pdf'
            next_version = max((row.version_number for row in note.versions), default=0) + 1
            db.add(
                NoteVersion(
                    note_id=note.id,
                    version_number=next_version,
                    drive_file_id=new_drive_file_id,
                    file_size=int(new_file_size),
                    mime_type='application/pdf',
                    uploaded_by=actor_id,
                )
            )

        sync_note_batches(db, note, parsed_batch_ids)
        sync_note_tags(db, note, parsed_tags)

        db.commit()
        db.refresh(note)
        invalidate_notes_cache()

        warning_message = None
        if has_new_file and old_drive_file_id and old_drive_file_id != note.drive_file_id:
            try:
                delete_file(old_drive_file_id, user_id=note.uploaded_by)
            except (DriveNotConnectedError, DriveStorageError) as exc:
                warning_message = f'Note updated but could not remove previous Drive file: {exc}'

        result = (
            db.query(Note)
            .options(joinedload(Note.batches), joinedload(Note.tags), joinedload(Note.versions), joinedload(Note.subject), joinedload(Note.chapter), joinedload(Note.topic))
            .filter(Note.id == note.id, Note.center_id == int(session.get('center_id') or 0))
            .first()
        )
        payload = {
            'ok': True,
            'note': serialize_note(result),
        }
        if warning_message:
            payload['warning'] = warning_message
        return payload
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/{note_id}/download')
def download_note(
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    session = _require_session(request)
    role = (session.get('role') or '').lower()

    note = (
        db.query(Note)
        .options(joinedload(Note.batches))
        .filter(Note.id == note_id, Note.center_id == int(session.get('center_id') or 0))
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail='Note not found')

    student = None
    matched_batch_id = None
    if role == Role.STUDENT.value:
        student = require_student_session(db, _resolve_token(request))['student']
        batch_ids = set(get_student_batch_ids(db, student, center_id=int(session.get('center_id') or 0)))
        note_batch_ids = {batch.id for batch in note.batches}
        allowed_batch_ids = sorted(batch_ids.intersection(note_batch_ids))
        if not allowed_batch_ids:
            raise HTTPException(status_code=403, detail='You do not have access to this note')
        matched_batch_id = allowed_batch_ids[0]
        now = default_time_provider.now().replace(tzinfo=None)
        if not note.visible_to_students:
            raise HTTPException(status_code=403, detail='Note is not visible to students')
        if note.release_at and note.release_at > now:
            raise HTTPException(status_code=403, detail='Note is not released yet')
        if note.expire_at and note.expire_at <= now:
            raise HTTPException(status_code=403, detail='Note has expired')

    try:
        payload = stream_file(note.drive_file_id, user_id=note.uploaded_by)
    except DriveNotConnectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DriveStorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    logger.warning('read_endpoint_side_effect_removed endpoint=/api/notes/%s/download side_effect=download_log_insert', note.id)

    headers: dict[str, Any] = {
        'Content-Disposition': f'attachment; filename="{note.title}.pdf"',
        'X-Accel-Buffering': 'no',
    }
    if payload.file_size:
        headers['Content-Length'] = str(payload.file_size)

    return StreamingResponse(
        payload.chunks,
        media_type=payload.mime_type or note.mime_type or 'application/pdf',
        headers=headers,
    )


@router.delete('/{note_id}')
def delete_note(
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    session = _require_teacher(request)

    note = (
        db.query(Note)
        .options(joinedload(Note.versions))
        .filter(Note.id == note_id, Note.center_id == int(session.get('center_id') or 0))
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail='Note not found')

    drive_file_ids = {
        *(version.drive_file_id for version in (note.versions or []) if version.drive_file_id),
        note.drive_file_id,
    }
    try:
        for drive_file_id in drive_file_ids:
            delete_file(drive_file_id, user_id=note.uploaded_by)
    except DriveNotConnectedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DriveStorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    db.delete(note)
    db.commit()
    invalidate_notes_cache()
    return {'ok': True, 'message': 'Note deleted'}
