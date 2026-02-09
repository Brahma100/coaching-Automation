import random
import string

from sqlalchemy.orm import Session

from app.models import ReferralCode


def _generate_code(length: int = 8) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def create_referral_code(db: Session, student_id: int):
    code = _generate_code()
    while db.query(ReferralCode).filter(ReferralCode.code == code).first():
        code = _generate_code()

    referral = ReferralCode(student_id=student_id, code=code, reward_points=0, usage_count=0)
    db.add(referral)
    db.commit()
    db.refresh(referral)
    return referral


def list_referrals(db: Session):
    return db.query(ReferralCode).order_by(ReferralCode.created_at.desc()).all()
