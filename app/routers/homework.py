from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.cache import cache
from app.db import get_db
from app.schemas import HomeworkCreateRequest, HomeworkSubmissionRequest
from app.services.homework_service import create_homework, list_homework, list_submissions, submit_homework


router = APIRouter(prefix='/homework', tags=['Homework'])


@router.post('/create')
def create(payload: HomeworkCreateRequest, db: Session = Depends(get_db)):
    row = create_homework(db, payload.model_dump())
    return {'id': row.id, 'title': row.title, 'due_date': str(row.due_date)}


@router.get('/list')
def list_all(db: Session = Depends(get_db)):
    rows = list_homework(db)
    return [
        {
            'id': h.id,
            'title': h.title,
            'description': h.description,
            'due_date': str(h.due_date),
            'attachment_path': h.attachment_path,
        }
        for h in rows
    ]


@router.post('/submit')
def submit(payload: HomeworkSubmissionRequest, db: Session = Depends(get_db)):
    row = submit_homework(db, payload.model_dump())
    cache.invalidate_prefix('student_dashboard')
    cache.invalidate_prefix('admin_ops')
    return {'id': row.id, 'homework_id': row.homework_id, 'student_id': row.student_id}


@router.get('/submissions/{homework_id}')
def submissions(homework_id: int, db: Session = Depends(get_db)):
    rows = list_submissions(db, homework_id)
    return [
        {
            'id': s.id,
            'homework_id': s.homework_id,
            'student_id': s.student_id,
            'file_path': s.file_path,
            'submitted_at': s.submitted_at.isoformat(),
        }
        for s in rows
    ]
