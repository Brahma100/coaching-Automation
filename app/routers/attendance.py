import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.router_guard import assert_center_match, assert_teacher_batch_scope, require_auth_user, require_role
from app.core.time_provider import default_time_provider
from app.db import get_db
from app.domain.services.attendance_service import submit_attendance as domain_submit_attendance
from app.models import Batch
from app.schemas import AttendanceSubmitRequest
from app.services.attendance_service import get_attendance_for_batch_today


router = APIRouter(prefix='/attendance', tags=['Attendance'])
logger = logging.getLogger(__name__)


@router.get('/batch/{batch_id}/today')
def attendance_for_today(batch_id: int, db: Session = Depends(get_db)):
    return get_attendance_for_batch_today(db, batch_id, default_time_provider.today())


@router.post('/submit')
def submit(payload: AttendanceSubmitRequest, request: Request, db: Session = Depends(get_db)):
    # DEPRECATED: legacy endpoint kept for backward compatibility.
    # TODO: remove /attendance/submit after clients migrate to /api/attendance/session/{session_id}/submit.
    logger.warning('deprecated_endpoint_used path=/attendance/submit')
    user = require_auth_user(request)
    require_role(user, {'teacher'})
    batch = db.query(Batch).filter(Batch.id == payload.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail='Batch not found')
    assert_center_match(user, int(batch.center_id or 0))
    assert_teacher_batch_scope(db, user, int(payload.batch_id))
    try:
        records = [r.model_dump() for r in payload.records]
        return domain_submit_attendance(
            db,
            batch_id=payload.batch_id,
            attendance_date=payload.attendance_date,
            records=records,
            subject=payload.subject,
            teacher_id=int(user['user_id']),
            scheduled_start=payload.scheduled_start,
            topic_planned=payload.topic_planned,
            topic_completed=payload.topic_completed,
            actor_role='teacher',
            actor_user_id=int(user['user_id']),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc) or 'Forbidden') from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
