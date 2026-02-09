from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import and_

from app.config import settings
from app.models import AttendanceRecord, ClassSession, FeeRecord, Homework, HomeworkSubmission, Parent, ParentStudentMap, PendingAction, Student, StudentBatchMap, StudentRiskProfile


def _time_window_for_day(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    return start, end


def _teacher_batch_ids(db, teacher_id: int) -> set[int]:
    if not teacher_id:
        return set()
    rows = db.query(ClassSession.batch_id).filter(ClassSession.teacher_id == teacher_id).distinct().all()
    return {batch_id for (batch_id,) in rows if batch_id is not None}


def _student_ids_for_teacher(db, teacher_id: int) -> set[int]:
    batch_ids = _teacher_batch_ids(db, teacher_id)
    if not batch_ids:
        return set()
    rows = (
        db.query(StudentBatchMap.student_id)
        .filter(
            StudentBatchMap.batch_id.in_(batch_ids),
            StudentBatchMap.active.is_(True),
        )
        .distinct()
        .all()
    )
    if not rows:
        rows = db.query(Student.id).filter(Student.batch_id.in_(batch_ids)).all()
    return {student_id for (student_id,) in rows}


def resolve_teacher_chat_id(db, teacher_phone: str) -> str:
    clean_phone = ''.join(ch for ch in (teacher_phone or '') if ch.isdigit())
    parent = db.query(Parent).filter(Parent.phone == clean_phone).first()
    if parent and parent.telegram_chat_id:
        return parent.telegram_chat_id
    return settings.auth_otp_fallback_chat_id


def get_today_classes_for_teacher(db, teacher_id: int, day: date | None = None) -> dict:
    day = day or date.today()
    start, end = _time_window_for_day(day)
    rows = (
        db.query(ClassSession)
        .filter(
            and_(
                ClassSession.teacher_id == teacher_id,
                ClassSession.scheduled_start >= start,
                ClassSession.scheduled_start < end,
            )
        )
        .order_by(ClassSession.scheduled_start.asc())
        .all()
    )
    classes = [
        {
            'session_id': row.id,
            'batch_id': row.batch_id,
            'subject': row.subject,
            'scheduled_start': row.scheduled_start.isoformat(),
            'status': row.status,
        }
        for row in rows
    ]
    sentence = 'No classes scheduled for today.'
    if classes:
        sentence = f"{len(classes)} class(es) scheduled today."
    return {'count': len(classes), 'classes': classes, 'sentence': sentence}


def get_absent_students_summary(db, teacher_id: int, day: date | None = None) -> dict:
    day = day or date.today()
    student_ids = _student_ids_for_teacher(db, teacher_id)
    if not student_ids:
        return {'count': 0, 'students': [], 'sentence': 'No mapped students for this teacher.'}

    rows = (
        db.query(AttendanceRecord, Student)
        .join(Student, Student.id == AttendanceRecord.student_id)
        .filter(
            and_(
                AttendanceRecord.attendance_date == day,
                AttendanceRecord.student_id.in_(student_ids),
                AttendanceRecord.status == 'Absent',
            )
        )
        .order_by(Student.name.asc())
        .all()
    )
    students = [
        {
            'student_id': student.id,
            'student_name': student.name,
            'comment': attendance.comment or '',
        }
        for attendance, student in rows
    ]
    sentence = 'No absent students recorded today.'
    if students:
        sentence = f"{len(students)} student(s) marked absent today."
    return {'count': len(students), 'students': students, 'sentence': sentence}


def get_pending_actions_summary(db, teacher_id: int) -> dict:
    rows = (
        db.query(PendingAction)
        .join(ClassSession, ClassSession.id == PendingAction.related_session_id, isouter=True)
        .filter(
            and_(
                PendingAction.status == 'open',
                ClassSession.teacher_id == teacher_id,
            )
        )
        .order_by(PendingAction.created_at.desc())
        .all()
    )
    actions = [
        {
            'action_id': row.id,
            'type': row.type,
            'student_id': row.student_id,
            'note': row.note,
            'created_at': row.created_at.isoformat(),
        }
        for row in rows
    ]
    sentence = 'No pending actions linked to your sessions.'
    if actions:
        sentence = f"{len(actions)} open action(s) need follow-up."
    return {'count': len(actions), 'actions': actions, 'sentence': sentence}


def get_fee_due_summary(db, teacher_id: int, current_month: date | None = None) -> dict:
    current_month = current_month or date.today()
    start = date(current_month.year, current_month.month, 1)
    next_month = date(current_month.year + (1 if current_month.month == 12 else 0), 1 if current_month.month == 12 else current_month.month + 1, 1)

    student_ids = _student_ids_for_teacher(db, teacher_id)
    if not student_ids:
        return {'count': 0, 'overdue_count': 0, 'rows': [], 'sentence': 'No mapped students for fee summary.'}

    today = date.today()
    rows = (
        db.query(FeeRecord, Student)
        .join(Student, Student.id == FeeRecord.student_id)
        .filter(
            and_(
                FeeRecord.student_id.in_(student_ids),
                FeeRecord.due_date >= start,
                FeeRecord.due_date < next_month,
                FeeRecord.is_paid.is_(False),
            )
        )
        .order_by(FeeRecord.due_date.asc())
        .all()
    )
    payload = []
    overdue_count = 0
    for fee, student in rows:
        is_overdue = fee.due_date < today
        if is_overdue:
            overdue_count += 1
        payload.append(
            {
                'student_id': student.id,
                'student_name': student.name,
                'due_date': fee.due_date.isoformat(),
                'amount_due': max(0.0, float(fee.amount) - float(fee.paid_amount)),
                'overdue': is_overdue,
            }
        )
    sentence = 'No unpaid fees due this month.'
    if payload:
        sentence = f"{len(payload)} unpaid fee record(s) this month ({overdue_count} overdue)."
    return {'count': len(payload), 'overdue_count': overdue_count, 'rows': payload, 'sentence': sentence}


def get_homework_summary(db, teacher_id: int, upcoming_due: int = 3) -> dict:
    student_ids = _student_ids_for_teacher(db, teacher_id)
    if not student_ids:
        return {'count': 0, 'rows': [], 'sentence': 'No mapped students for homework summary.'}

    today = date.today()
    end_date = today + timedelta(days=upcoming_due)
    rows = (
        db.query(Homework)
        .filter(
            and_(
                Homework.due_date >= today,
                Homework.due_date <= end_date,
            )
        )
        .order_by(Homework.due_date.asc())
        .all()
    )

    payload = []
    for hw in rows:
        submitted_count = (
            db.query(HomeworkSubmission.homework_id)
            .filter(
                and_(
                    HomeworkSubmission.homework_id == hw.id,
                    HomeworkSubmission.student_id.in_(student_ids),
                )
            )
            .distinct()
            .count()
        )
        pending_count = max(0, len(student_ids) - submitted_count)
        payload.append(
            {
                'homework_id': hw.id,
                'title': hw.title,
                'due_date': hw.due_date.isoformat(),
                'submitted_count': submitted_count,
                'pending_count': pending_count,
            }
        )
    sentence = f'No homework due in the next {upcoming_due} day(s).'
    if payload:
        sentence = f"{len(payload)} homework item(s) due in the next {upcoming_due} day(s)."
    return {'count': len(payload), 'rows': payload, 'sentence': sentence}


def get_risk_summary(db, teacher_id: int) -> dict:
    student_ids = _student_ids_for_teacher(db, teacher_id)
    if not student_ids:
        return {'count': 0, 'students': [], 'sentence': 'No mapped students for risk summary.'}

    rows = (
        db.query(StudentRiskProfile, Student)
        .join(Student, Student.id == StudentRiskProfile.student_id)
        .filter(
            and_(
                StudentRiskProfile.student_id.in_(student_ids),
                StudentRiskProfile.risk_level == 'HIGH',
            )
        )
        .order_by(StudentRiskProfile.final_risk_score.asc())
        .all()
    )
    students = [
        {
            'student_id': student.id,
            'student_name': student.name,
            'risk_score': profile.final_risk_score,
        }
        for profile, student in rows
    ]
    sentence = 'No HIGH risk students currently.'
    if students:
        sentence = f"{len(students)} HIGH risk student(s) require attention."
    return {'count': len(students), 'students': students, 'sentence': sentence}


def build_daily_teacher_brief(db, teacher_id: int, day: date | None = None, upcoming_due: int = 3) -> dict:
    day = day or date.today()
    class_schedule = get_today_classes_for_teacher(db, teacher_id, day=day)
    absent_students = get_absent_students_summary(db, teacher_id, day=day)
    pending_actions = get_pending_actions_summary(db, teacher_id)
    fee_due = get_fee_due_summary(db, teacher_id, current_month=day)
    homework_due = get_homework_summary(db, teacher_id, upcoming_due=upcoming_due)
    high_risk_students = get_risk_summary(db, teacher_id)
    return {
        'date': day.isoformat(),
        'class_schedule': class_schedule,
        'absent_students': absent_students,
        'pending_actions': pending_actions,
        'fee_due': fee_due,
        'homework_due': homework_due,
        'high_risk_students': high_risk_students,
    }


def format_daily_teacher_brief(summary: dict, teacher_phone: str) -> str:
    lines = [
        f"Daily Teacher Brief ({summary['date']})",
        f"Teacher: {teacher_phone}",
        '',
        f"Class Schedule: {summary['class_schedule']['sentence']}",
        f"Absent Students: {summary['absent_students']['sentence']}",
        f"Pending Actions: {summary['pending_actions']['sentence']}",
        f"Fee Dues: {summary['fee_due']['sentence']}",
        f"Homework: {summary['homework_due']['sentence']}",
        f"Risk: {summary['high_risk_students']['sentence']}",
    ]

    top_absent = summary['absent_students']['students'][:3]
    if top_absent:
        lines.append("Absent list: " + ', '.join(row['student_name'] for row in top_absent))

    top_risk = summary['high_risk_students']['students'][:3]
    if top_risk:
        lines.append("HIGH risk: " + ', '.join(row['student_name'] for row in top_risk))

    return '\n'.join(lines)
