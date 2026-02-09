from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import OfferApplyRequest, OfferCreateRequest
from app.services.offer_service import apply_offer_to_fee, create_offer, list_offers


router = APIRouter(prefix='/offers', tags=['Offers'])


@router.post('/create')
def create(payload: OfferCreateRequest, db: Session = Depends(get_db)):
    row = create_offer(db, payload.model_dump())
    return {'id': row.id, 'code': row.code, 'active': row.active}


@router.get('/list')
def list_all(active_only: bool = False, db: Session = Depends(get_db)):
    rows = list_offers(db, active_only=active_only)
    return [
        {
            'id': r.id,
            'code': r.code,
            'title': r.title,
            'discount_type': r.discount_type,
            'discount_value': r.discount_value,
            'valid_from': str(r.valid_from),
            'valid_to': str(r.valid_to),
            'active': r.active,
        }
        for r in rows
    ]


@router.post('/apply')
def apply(payload: OfferApplyRequest, db: Session = Depends(get_db)):
    try:
        return apply_offer_to_fee(
            db,
            code=payload.code,
            student_id=payload.student_id,
            fee_record_id=payload.fee_record_id,
            referral_code=payload.referral_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
