from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ReferralCreateRequest
from app.services.referral_service import create_referral_code, list_referrals


router = APIRouter(prefix='/referral', tags=['Referrals'])


@router.post('/create')
def create(payload: ReferralCreateRequest, db: Session = Depends(get_db)):
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
