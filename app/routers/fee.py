from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import FeeMarkPaidRequest
from app.services.fee_service import get_fee_dashboard, mark_fee_paid


router = APIRouter(prefix='/fee', tags=['Fees'])


@router.get('/dashboard')
def fee_dashboard(db: Session = Depends(get_db)):
    return get_fee_dashboard(db)


@router.post('/mark-paid')
def mark_paid(payload: FeeMarkPaidRequest, db: Session = Depends(get_db)):
    try:
        return mark_fee_paid(db, payload.fee_record_id, payload.paid_amount)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
