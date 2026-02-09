from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ClassSessionCreateRequest, ClassSessionUpdateRequest
from app.services.class_session_service import complete_class_session, create_class_session, get_session, list_batch_sessions, start_class_session


router = APIRouter(prefix='/class-sessions', tags=['Class Sessions'])


@router.post('/create')
def create(payload: ClassSessionCreateRequest, db: Session = Depends(get_db)):
    row = create_class_session(
        db,
        batch_id=payload.batch_id,
        subject=payload.subject,
        scheduled_start=payload.scheduled_start,
        teacher_id=payload.teacher_id,
        topic_planned=payload.topic_planned,
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
            'status': r.status,
            'teacher_id': r.teacher_id,
        }
        for r in rows
    ]


@router.post('/start/{session_id}')
def start(session_id: int, db: Session = Depends(get_db)):
    try:
        row = start_class_session(db, session_id)
        return {'id': row.id, 'status': row.status, 'actual_start': row.actual_start}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post('/complete/{session_id}')
def complete(session_id: int, payload: ClassSessionUpdateRequest, db: Session = Depends(get_db)):
    try:
        row = complete_class_session(db, session_id, topic_completed=payload.topic_completed)
        if payload.status in ('completed', 'missed'):
            row.status = payload.status
            db.commit()
            db.refresh(row)
        return {'id': row.id, 'status': row.status, 'topic_completed': row.topic_completed}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
