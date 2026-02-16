from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.router_guard import (
    assert_center_match,
    assert_teacher_batch_scope,
    assert_teacher_session_scope,
    require_auth_user,
    require_role,
)
from app.db import get_db
from app.models import Batch
from app.schemas import ClassSessionCreateRequest, ClassSessionUpdateRequest
from app.services.class_session_service import complete_class_session, create_class_session, get_session, list_batch_sessions, start_class_session


router = APIRouter(prefix='/class-sessions', tags=['Class Sessions'])


@router.post('/create')
def create(payload: ClassSessionCreateRequest, request: Request, db: Session = Depends(get_db)):
    user = require_auth_user(request)
    require_role(user, {'admin', 'teacher'})
    batch = db.query(Batch).filter(Batch.id == payload.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail='Batch not found')
    assert_center_match(user, int(batch.center_id or 0))
    assert_teacher_batch_scope(db, user, payload.batch_id)
    teacher_id = int(payload.teacher_id)
    if user['role'] == 'teacher':
        teacher_id = int(user['user_id'])
    row = create_class_session(
        db,
        batch_id=payload.batch_id,
        subject=payload.subject,
        scheduled_start=payload.scheduled_start,
        teacher_id=teacher_id,
        topic_planned=payload.topic_planned,
        duration_minutes=payload.duration_minutes,
    )
    return {'id': row.id, 'status': row.status}


@router.get('/{session_id}')
def get_one(session_id: int, db: Session = Depends(get_db)):
    row = get_session(db, session_id)
    if not row:
        raise HTTPException(status_code=404, detail='Class session not found')
    return {
        'id': row.id,
        'batch_id': row.batch_id,
        'subject': row.subject,
        'scheduled_start': row.scheduled_start,
        'duration_minutes': row.duration_minutes,
        'actual_start': row.actual_start,
        'topic_planned': row.topic_planned,
        'topic_completed': row.topic_completed,
        'teacher_id': row.teacher_id,
        'status': row.status,
    }


@router.get('/batch/{batch_id}')
def list_batch(batch_id: int, db: Session = Depends(get_db)):
    rows = list_batch_sessions(db, batch_id)
    return [
        {
            'id': r.id,
            'subject': r.subject,
            'scheduled_start': r.scheduled_start,
            'duration_minutes': r.duration_minutes,
            'status': r.status,
            'teacher_id': r.teacher_id,
        }
        for r in rows
    ]


@router.post('/start/{session_id}')
def start(session_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_auth_user(request)
    require_role(user, {'admin', 'teacher'})
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail='Class session not found')
    assert_teacher_session_scope(db, user, session)
    try:
        row = start_class_session(db, session_id)
        return {'id': row.id, 'status': row.status, 'actual_start': row.actual_start}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post('/complete/{session_id}')
def complete(session_id: int, payload: ClassSessionUpdateRequest, request: Request, db: Session = Depends(get_db)):
    user = require_auth_user(request)
    require_role(user, {'admin', 'teacher'})
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail='Class session not found')
    assert_teacher_session_scope(db, user, session)
    try:
        row = complete_class_session(db, session_id, topic_completed=payload.topic_completed)
        if payload.status in ('submitted', 'closed', 'missed', 'completed', 'running', 'open'):
            if payload.status == 'completed':
                row.status = 'submitted'
            elif payload.status == 'running':
                row.status = 'open'
            else:
                row.status = payload.status
            db.commit()
            db.refresh(row)
        return {'id': row.id, 'status': row.status, 'topic_completed': row.topic_completed}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
