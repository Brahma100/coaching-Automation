from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.router_guard import assert_center_match, assert_teacher_batch_scope, require_auth_user, require_role
from app.db import get_db
from app.models import Student
from app.schemas import ReferralCreateRequest
from app.services.referral_service import create_referral_code, list_referrals


router = APIRouter(prefix='/referral', tags=['Referrals'])


@router.post('/create')
def create(payload: ReferralCreateRequest, request: Request, db: Session = Depends(get_db)):
    user = require_auth_user(request)
    require_role(user, {'admin', 'teacher'})
    student = db.query(Student).filter(Student.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail='Student not found')
    assert_center_match(user, int(student.center_id or 0))
    assert_teacher_batch_scope(db, user, int(student.batch_id or 0))
    row = create_referral_code(db, payload.student_id)
    return {'id': row.id, 'student_id': row.student_id, 'code': row.code, 'reward_points': row.reward_points}


@router.get('/list')
def list_all(db: Session = Depends(get_db)):
    rows = list_referrals(db)
    return [
        {
            'id': r.id,
            'student_id': r.student_id,
            'code': r.code,
            'usage_count': r.usage_count,
            'reward_points': r.reward_points,
        }
        for r in rows
    ]
