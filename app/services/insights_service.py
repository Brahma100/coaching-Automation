from datetime import timedelta
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import settings
from app.core.time_provider import TimeProvider, default_time_provider
from app.models import AttendanceRecord, FeeRecord, Student


def generate_insights(db: Session, *, time_provider: TimeProvider = default_time_provider):
    today = time_provider.today()
    month_start = today - timedelta(days=30)

    attendance_rows = db.query(
        AttendanceRecord.student_id,
        func.count(AttendanceRecord.id).label('total'),
        func.sum(case((AttendanceRecord.status == 'Present', 1), else_=0)).label('present_count'),
    ).filter(AttendanceRecord.attendance_date >= month_start).group_by(AttendanceRecord.student_id).all()

    low_attendance = []
    for row in attendance_rows:
        if not row.total:
            continue
        ratio = (row.present_count or 0) / row.total
        if ratio < settings.attendance_low_threshold:
            student = db.query(Student).filter(Student.id == row.student_id).first()
            low_attendance.append({
                'student_id': row.student_id,
                'student_name': student.name if student else 'Unknown',
                'attendance_ratio': round(ratio, 2),
            })

    unpaid = db.query(FeeRecord).filter(FeeRecord.is_paid.is_(False)).all()
    unpaid_fees = [
        {
            'fee_record_id': f.id,
            'student_id': f.student_id,
            'pending_amount': round(f.amount - f.paid_amount, 2),
            'due_date': str(f.due_date),
        }
        for f in unpaid
    ]

    return {'low_attendance': low_attendance, 'unpaid_fees': unpaid_fees}
