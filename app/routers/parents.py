from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ParentCreateRequest, ParentStudentLinkRequest
from app.services.parent_service import create_parent, link_parent_student


router = APIRouter(prefix='/parents', tags=['Parents'])


@router.post('/create')
def create(payload: ParentCreateRequest, db: Session = Depends(get_db)):
    row = create_parent(db, name=payload.name, phone=payload.phone, telegram_chat_id=payload.telegram_chat_id)
    return {'id': row.id, 'name': row.name, 'phone': row.phone}


@router.post('/link-student')
def link_student(payload: ParentStudentLinkRequest, db: Session = Depends(get_db)):
    row = link_parent_student(db, parent_id=payload.parent_id, student_id=payload.student_id, relation=payload.relation)
    return {'id': row.id, 'parent_id': row.parent_id, 'student_id': row.student_id, 'relation': row.relation}
