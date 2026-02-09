from datetime import date

from sqlalchemy.orm import Session

from app.models import FeeRecord, Offer, OfferRedemption, ReferralCode


def create_offer(db: Session, payload: dict):
    row = Offer(**payload)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_offers(db: Session, active_only: bool = False):
    q = db.query(Offer)
    if active_only:
        q = q.filter(Offer.active.is_(True))
    return q.order_by(Offer.id.desc()).all()


def _calculate_discount(amount: float, discount_type: str, discount_value: float) -> float:
    if discount_type == 'percent':
        return round(amount * (discount_value / 100.0), 2)
    return round(discount_value, 2)


def apply_offer_to_fee(db: Session, code: str, student_id: int, fee_record_id: int, referral_code: str | None = None):
    today = date.today()
    offer = db.query(Offer).filter(Offer.code == code, Offer.active.is_(True)).first()
    if not offer:
        raise ValueError('Offer not found')
    if offer.valid_from > today or offer.valid_to < today:
        raise ValueError('Offer is not currently valid')

    fee = db.query(FeeRecord).filter(FeeRecord.id == fee_record_id, FeeRecord.student_id == student_id).first()
    if not fee:
        raise ValueError('Fee record not found')

    discount = _calculate_discount(fee.amount, offer.discount_type, offer.discount_value)
    max_discount = max(0.0, fee.amount - fee.paid_amount)
    discount = min(discount, max_discount)
    fee.amount = max(fee.paid_amount, fee.amount - discount)

    referral_id = None
    if referral_code:
        referral = db.query(ReferralCode).filter(ReferralCode.code == referral_code, ReferralCode.student_id == student_id).first()
        if referral:
            referral.usage_count += 1
            referral.reward_points += int(discount)
            referral_id = referral.id

    redemption = OfferRedemption(
        offer_id=offer.id,
        student_id=student_id,
        fee_record_id=fee.id,
        referral_code_id=referral_id,
        discount_amount=discount,
    )
    db.add(redemption)
    db.commit()
    db.refresh(redemption)

    return {
        'offer_code': offer.code,
        'student_id': student_id,
        'fee_record_id': fee.id,
        'discount_amount': discount,
        'new_fee_amount': fee.amount,
    }
