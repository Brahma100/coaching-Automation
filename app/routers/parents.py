from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.router_guard import assert_center_match, assert_teacher_batch_scope, require_auth_user, require_role
from app.db import get_db
from app.models import Parent, Student
from app.schemas import ParentCreateRequest, ParentStudentLinkRequest
from app.services.parent_service import create_parent, link_parent_student


router = APIRouter(prefix='/parents', tags=['Parents'])


@router.post('/create')
def create(payload: ParentCreateRequest, request: Request, db: Session = Depends(get_db)):
    user = require_auth_user(request)
    require_role(user, {'admin', 'teacher'})
    row = create_parent(
        db,
        name=payload.name,
        phone=payload.phone,
        telegram_chat_id=payload.telegram_chat_id,
        center_id=int(user['center_id']),
    )
    return {'id': row.id, 'name': row.name, 'phone': row.phone}


@router.post('/link-student')
def link_student(payload: ParentStudentLinkRequest, request: Request, db: Session = Depends(get_db)):
    user = require_auth_user(request)
    require_role(user, {'admin', 'teacher'})
    parent = db.query(Parent).filter(Parent.id == payload.parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail='Parent not found')
    student = db.query(Student).filter(Student.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail='Student not found')
    assert_center_match(user, int(parent.center_id or 0))
    assert_center_match(user, int(student.center_id or 0))
    if int(parent.center_id or 0) != int(student.center_id or 0):
        raise HTTPException(status_code=403, detail='Forbidden')
    assert_teacher_batch_scope(db, user, int(student.batch_id or 0))
    try:
        row = link_parent_student(db, parent_id=payload.parent_id, student_id=payload.student_id, relation=payload.relation)
    except ValueError as exc:
        detail = str(exc) or 'Forbidden'
        code = 403 if 'same center' in detail else 404
        raise HTTPException(status_code=code, detail=detail) from exc
    return {'id': row.id, 'parent_id': row.parent_id, 'student_id': row.student_id, 'relation': row.relation}
