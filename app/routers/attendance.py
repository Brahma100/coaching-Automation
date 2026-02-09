from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import AttendanceSubmitRequest
from app.services.attendance_service import get_attendance_for_batch_today, submit_attendance


router = APIRouter(prefix='/attendance', tags=['Attendance'])


@router.get('/batch/{batch_id}/today')
def attendance_for_today(batch_id: int, db: Session = Depends(get_db)):
    return get_attendance_for_batch_today(db, batch_id, date.today())


@router.post('/submit')
def submit(payload: AttendanceSubmitRequest, db: Session = Depends(get_db)):
    try:
        records = [r.model_dump() for r in payload.records]
        return submit_attendance(
            db,
            payload.batch_id,
            payload.attendance_date,
            records,
            subject=payload.subject,
            teacher_id=payload.teacher_id,
            scheduled_start=payload.scheduled_start,
            topic_planned=payload.topic_planned,
            topic_completed=payload.topic_completed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
