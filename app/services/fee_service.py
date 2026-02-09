from datetime import date
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.config import settings
from app.models import FeeRecord, Student
from app.services.comms_service import send_fee_reminder


def build_upi_link(student: Student, amount: float) -> str:
    return f"upi://pay?pa={settings.default_upi_id}&pn=Coaching&am={amount:.2f}&tn=Fee-{student.id}"


def get_fee_dashboard(db: Session):
    today = date.today()
    all_fees = db.query(FeeRecord).all()
    due, paid, overdue = [], [], []

    for fee in all_fees:
        item = {
            'id': fee.id,
            'student_id': fee.student_id,
            'amount': fee.amount,
            'paid_amount': fee.paid_amount,
            'due_date': str(fee.due_date),
            'upi_link': fee.upi_link,
            'is_paid': fee.is_paid,
        }
        if fee.is_paid:
            paid.append(item)
        elif fee.due_date < today:
            overdue.append(item)
        else:
            due.append(item)

    return {'due': due, 'paid': paid, 'overdue': overdue}


def mark_fee_paid(db: Session, fee_record_id: int, paid_amount: float):
    fee = db.query(FeeRecord).filter(FeeRecord.id == fee_record_id).first()
    if not fee:
        raise ValueError('Fee record not found')

    fee.paid_amount += paid_amount
    fee.is_paid = fee.paid_amount >= fee.amount
    db.commit()
    return {'fee_record_id': fee.id, 'is_paid': fee.is_paid, 'paid_amount': fee.paid_amount}


def trigger_fee_reminders(db: Session):
    today = date.today()
    pending = db.query(FeeRecord).filter(
        and_(FeeRecord.is_paid.is_(False), FeeRecord.due_date <= today)
    ).all()

    for fee in pending:
        student = db.query(Student).filter(Student.id == fee.student_id).first()
        if not student:
            continue
        if not fee.upi_link:
            fee.upi_link = build_upi_link(student, fee.amount - fee.paid_amount)
            db.commit()
        send_fee_reminder(db, student, fee.amount - fee.paid_amount, fee.upi_link)

    return len(pending)
