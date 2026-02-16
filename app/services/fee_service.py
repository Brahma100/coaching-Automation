from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.config import settings
from app.core.time_provider import TimeProvider, default_time_provider
from app.models import FeeRecord, Student
from app.services.comms_service import send_fee_reminder
from app.services.inbox_automation import resolve_fee_actions_on_paid
from app.services import snapshot_service


def build_upi_link(student: Student, amount: float) -> str:
    return f"upi://pay?pa={settings.default_upi_id}&pn=Coaching&am={amount:.2f}&tn=Fee-{student.id}"


def get_fee_dashboard(db: Session, *, time_provider: TimeProvider = default_time_provider):
    today = time_provider.today()
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


def mark_fee_paid(
    db: Session,
    fee_record_id: int,
    paid_amount: float,
    *,
    time_provider: TimeProvider = default_time_provider,
):
    fee = db.query(FeeRecord).filter(FeeRecord.id == fee_record_id).first()
    if not fee:
        raise ValueError('Fee record not found')

    fee.paid_amount += paid_amount
    fee.is_paid = fee.paid_amount >= fee.amount
    db.commit()
    if fee.is_paid:
        resolve_fee_actions_on_paid(db, student_id=fee.student_id)

    # CQRS-lite snapshots: best-effort refresh (never break the write path).
    try:
        today = time_provider.today()
        snapshot_service.refresh_student_dashboard_snapshot(db, student_id=int(fee.student_id), day=today)
        for teacher_id in snapshot_service.teacher_ids_for_student_today(db, student_id=int(fee.student_id), day=today):
            snapshot_service.refresh_teacher_today_snapshot(db, teacher_id=teacher_id, day=today)
        snapshot_service.refresh_admin_ops_snapshot(db, day=today)
    except Exception:
        pass
    return {'fee_record_id': fee.id, 'is_paid': fee.is_paid, 'paid_amount': fee.paid_amount}


def trigger_fee_reminders(db: Session, *, center_id: int, time_provider: TimeProvider = default_time_provider):
    center_id = int(center_id or 0)
    if center_id <= 0:
        raise ValueError('center_id is required')
    today = time_provider.today()
    pending = (
        db.query(FeeRecord)
        .join(Student, Student.id == FeeRecord.student_id)
        .filter(
            and_(
                FeeRecord.is_paid.is_(False),
                FeeRecord.due_date <= today,
                Student.center_id == center_id,
            )
        )
        .all()
    )

    for fee in pending:
        student = db.query(Student).filter(Student.id == fee.student_id, Student.center_id == center_id).first()
        if not student:
            continue
        if not fee.upi_link:
            fee.upi_link = build_upi_link(student, fee.amount - fee.paid_amount)
            db.commit()
        send_fee_reminder(db, student, fee.amount - fee.paid_amount, fee.upi_link)

    return len(pending)
