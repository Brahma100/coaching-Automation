from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import and_

from app.models import (
    AttendanceRecord,
    ClassSession,
    FeeRecord,
    Homework,
    HomeworkSubmission,
    Parent,
    ParentStudentMap,
    Role,
    Student,
    StudentBatchMap,
)
from app.services.auth_service import validate_session_token


def normalize_phone(value: str) -> str:
    return ''.join(ch for ch in (value or '') if ch.isdigit())


def require_student_session(db, token: str | None) -> dict:
    # Read-only by design: only student-role sessions can access student portal.
    session = validate_session_token(token)
    if not session:
        raise PermissionError('Unauthorized')

    if (session.get('role') or '').lower() != Role.STUDENT.value:
        raise PermissionError('Student access required')

    student = resolve_student_for_session(db, session)
    return {'session': session, 'student': student}


def resolve_student_for_session(db, session: dict) -> Student:
    # Read-only by design: derive identity from session phone only (never from request params).
    phone = normalize_phone(session.get('phone') or '')
    if not phone:
        raise PermissionError('Student profile not linked to this session')

    direct_ids = {
        row.id
        for row in db.query(Student).filter(Student.guardian_phone == phone).all()
    }

    parent_ids = {
        row.id
        for row in db.query(Parent).filter(Parent.phone == phone).all()
    }
    linked_ids = set()
    if parent_ids:
        linked_ids = {
            row.student_id
            for row in db.query(ParentStudentMap).filter(ParentStudentMap.parent_id.in_(parent_ids)).all()
        }

    student_ids = direct_ids.union(linked_ids)
    if not student_ids:
        raise PermissionError('No student profile is linked to this phone')
    if len(student_ids) > 1:
        raise PermissionError('Multiple student profiles linked to this phone')

    student = db.query(Student).filter(Student.id == list(student_ids)[0]).first()
    if not student:
        raise PermissionError('Student profile not found')
    return student


def get_student_dashboard(db, student: Student) -> dict:
    # Read-only by design: aggregates only this student's data.
    attendance_rows = db.query(AttendanceRecord).filter(AttendanceRecord.student_id == student.id).all()
    total_attendance = len(attendance_rows)
    present = sum(1 for row in attendance_rows if row.status == 'Present')
    absent = sum(1 for row in attendance_rows if row.status == 'Absent')
    late = sum(1 for row in attendance_rows if row.status == 'Late')
    attendance_pct = round((present / total_attendance) * 100, 1) if total_attendance else 0.0

    homework_total = db.query(Homework).count()
    submitted_homework = (
        db.query(HomeworkSubmission.homework_id)
        .filter(HomeworkSubmission.student_id == student.id)
        .distinct()
        .count()
    )
    pending_homework = max(0, homework_total - submitted_homework)

    today = date.today()
    fee_rows = db.query(FeeRecord).filter(FeeRecord.student_id == student.id).all()
    paid_fees = sum(1 for row in fee_rows if row.is_paid or row.paid_amount >= row.amount)
    due_fees = sum(1 for row in fee_rows if not row.is_paid and row.due_date >= today)
    overdue_fees = sum(1 for row in fee_rows if not row.is_paid and row.due_date < today)

    upcoming_tests = []
    batch_ids = {
        batch_id
        for (batch_id,) in (
            db.query(StudentBatchMap.batch_id)
            .filter(
                StudentBatchMap.student_id == student.id,
                StudentBatchMap.active.is_(True),
            )
            .all()
        )
    }
    if not batch_ids and student.batch_id:
        batch_ids.add(student.batch_id)

    if batch_ids:
        rows = (
            db.query(ClassSession)
            .filter(and_(ClassSession.batch_id.in_(batch_ids), ClassSession.scheduled_start >= datetime.utcnow()))
            .order_by(ClassSession.scheduled_start.asc())
            .limit(5)
            .all()
        )
        upcoming_tests = [
            {
                'subject': row.subject,
                'scheduled_start': row.scheduled_start.isoformat(),
                'topic_planned': row.topic_planned,
            }
            for row in rows
        ]

    return {
        'attendance': {
            'percentage': attendance_pct,
            'present_count': present,
            'absent_count': absent,
            'late_count': late,
            'total_count': total_attendance,
        },
        'homework': {
            'assigned_count': homework_total,
            'submitted_count': submitted_homework,
            'pending_count': pending_homework,
        },
        'fees': {
            'paid_count': paid_fees,
            'due_count': due_fees,
            'overdue_count': overdue_fees,
        },
        'upcoming_tests': upcoming_tests,
    }


def list_student_attendance(db, student: Student, limit: int = 50) -> list[dict]:
    # Read-only by design: only returns records for the resolved student.
    rows = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.student_id == student.id)
        .order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            'date': row.attendance_date.isoformat(),
            'status': row.status,
            'comment': row.comment or '',
        }
        for row in rows
    ]


def list_student_homework(db, student: Student, limit: int = 100) -> list[dict]:
    # Read-only by design: assignment list + submission status for this student only.
    submitted_ids = {
        row.homework_id
        for row in db.query(HomeworkSubmission).filter(HomeworkSubmission.student_id == student.id).all()
    }
    rows = db.query(Homework).order_by(Homework.due_date.desc(), Homework.id.desc()).limit(limit).all()
    return [
        {
            'subject': 'General',
            'title': row.title,
            'assigned_date': row.created_at.date().isoformat() if row.created_at else '',
            'due_date': row.due_date.isoformat(),
            'submission_status': 'Submitted' if row.id in submitted_ids else 'Pending',
        }
        for row in rows
    ]


def list_student_fees(db, student: Student) -> list[dict]:
    # Read-only by design: fee rows scoped to the resolved student.
    today = date.today()
    rows = (
        db.query(FeeRecord)
        .filter(FeeRecord.student_id == student.id)
        .order_by(FeeRecord.due_date.desc(), FeeRecord.id.desc())
        .all()
    )
    payload = []
    for row in rows:
        status = 'Paid'
        if not row.is_paid:
            status = 'Overdue' if row.due_date < today else 'Due'
        payload.append(
            {
                'month': row.due_date.strftime('%b %Y'),
                'total_fee': row.amount,
                'paid_amount': row.paid_amount,
                'status': status,
                'due_date': row.due_date.isoformat(),
            }
        )
    return payload
