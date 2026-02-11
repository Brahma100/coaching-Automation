from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.frontend_routes import attendance_session_url, session_summary_url
from app.models import (
    AttendanceRecord,
    Batch,
    BatchSchedule,
    ClassSession,
    FeeRecord,
    PendingAction,
    Student,
    StudentBatchMap,
    StudentRiskProfile,
)
from app.cache import cache
from app.services.action_token_service import create_action_token
from app.metrics import timed_service


logger = logging.getLogger(__name__)


def clear_today_view_cache() -> None:
    cache.invalidate_prefix('today_view')


def _student_ids_for_teacher(db: Session, teacher_id: int) -> set[int]:
    if not teacher_id:
        return set()
    batch_rows = db.query(ClassSession.batch_id).filter(ClassSession.teacher_id == teacher_id).distinct().all()
    batch_ids = {batch_id for (batch_id,) in batch_rows if batch_id is not None}
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
    if rows:
        return {student_id for (student_id,) in rows}
    fallback = db.query(Student.id).filter(Student.batch_id.in_(batch_ids)).all()
    return {student_id for (student_id,) in fallback}


def _teacher_batch_ids(db: Session, teacher_id: int) -> set[int]:
    rows = db.query(ClassSession.batch_id).filter(ClassSession.teacher_id == teacher_id).distinct().all()
    return {batch_id for (batch_id,) in rows if batch_id is not None}


def _action_payload(
    db: Session,
    row: PendingAction,
    student_map: dict,
    session_map: dict,
    batch_map: dict,
    now: datetime,
    teacher_id: int | None,
) -> dict:
    due_at = row.due_at
    overdue_by_hours = None
    if due_at and due_at < now:
        overdue_by_hours = round((now - due_at).total_seconds() / 3600.0, 1)

    session = session_map.get(row.session_id or row.related_session_id)
    batch = batch_map.get(session.batch_id) if session else None
    summary_url = None
    if row.action_type == 'review_session_summary' and session:
        token = create_action_token(
            db=db,
            action_type='session_summary',
            payload={'session_id': session.id, 'teacher_id': teacher_id, 'role': 'teacher'},
            ttl_minutes=24 * 60,
        )['token']
        summary_url = session_summary_url(session.id, token)

    student = student_map.get(row.student_id)
    return {
        'id': row.id,
        'action_type': row.action_type or row.type,
        'status': row.status,
        'student_id': row.student_id,
        'student_name': student.name if student else None,
        'session_id': row.session_id or row.related_session_id,
        'batch_id': batch.id if batch else None,
        'batch_name': batch.name if batch else None,
        'due_at': row.due_at.isoformat() if row.due_at else None,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'resolved_at': row.resolved_at.isoformat() if row.resolved_at else None,
        'overdue_by_hours': overdue_by_hours,
        'summary_url': summary_url,
        'resolution_note': row.resolution_note or None,
        'escalation_sent_at': row.escalation_sent_at.isoformat() if row.escalation_sent_at else None,
        'note': row.note,
    }


def _build_today_classes(
    db: Session,
    *,
    today: date,
    now: datetime,
    batch_scope: set[int] | None,
    teacher_id: int | None,
) -> list[dict]:
    weekday = today.weekday()
    schedule_query = (
        db.query(BatchSchedule, Batch)
        .join(Batch, Batch.id == BatchSchedule.batch_id)
        .filter(BatchSchedule.weekday == weekday, Batch.active.is_(True))
        .order_by(BatchSchedule.start_time.asc(), BatchSchedule.id.asc())
    )
    if batch_scope:
        schedule_query = schedule_query.filter(BatchSchedule.batch_id.in_(batch_scope))
    schedules = schedule_query.all()
    if not schedules:
        return []

    day_start = datetime.combine(today, time.min)
    day_end = datetime.combine(today, time.max)
    batch_ids = {batch.id for _, batch in schedules}
    sessions = (
        db.query(ClassSession)
        .filter(
            ClassSession.batch_id.in_(batch_ids),
            ClassSession.scheduled_start >= day_start,
            ClassSession.scheduled_start <= day_end,
        )
        .all()
    )
    by_key = {(s.batch_id, s.scheduled_start): s for s in sessions}
    payload = []
    for schedule, batch in schedules:
        start_time = datetime.combine(today, datetime.strptime(schedule.start_time, '%H:%M').time())
        session = by_key.get((batch.id, start_time))
        status_label = 'not_started'
        if session:
            if session.status in ('submitted', 'closed'):
                status_label = 'submitted'
            elif session.status in ('missed',):
                status_label = 'pending'
            elif now < session.scheduled_start:
                status_label = 'not_started'
            else:
                status_label = 'pending'
        else:
            status_label = 'not_started' if now < start_time else 'pending'

        attendance_url = None
        summary_url = None
        if session:
            end_time = session.scheduled_start + timedelta(minutes=session.duration_minutes or 60)
            ttl_minutes = int(max(1, (end_time + timedelta(minutes=10) - datetime.utcnow()).total_seconds() // 60))
            token = create_action_token(
                db=db,
                action_type='attendance_open',
                payload={
                    'session_id': session.id,
                    'batch_id': batch.id,
                    'schedule_id': schedule.id,
                    'teacher_id': teacher_id or 0,
                    'role': 'teacher',
                },
                ttl_minutes=ttl_minutes,
            )['token']
            attendance_url = attendance_session_url(session.id, token)
            token_summary = create_action_token(
                db=db,
                action_type='session_summary',
                payload={'session_id': session.id, 'teacher_id': teacher_id or 0, 'role': 'teacher'},
                ttl_minutes=24 * 60,
            )['token']
            summary_url = session_summary_url(session.id, token_summary)

        payload.append(
            {
                'batch_id': batch.id,
                'batch_name': batch.name,
                'schedule_id': schedule.id,
                'session_id': session.id if session else None,
                'scheduled_start': start_time.isoformat(),
                'duration_minutes': schedule.duration_minutes,
                'attendance_status': status_label,
                'attendance_url': attendance_url,
                'summary_url': summary_url,
            }
        )
    return payload


def _build_flags(db: Session, *, today: date, student_scope: set[int] | None) -> dict:
    fee_due_present = []
    present_query = db.query(AttendanceRecord.student_id).filter(
        AttendanceRecord.attendance_date == today,
        AttendanceRecord.status == 'Present',
    )
    if student_scope:
        present_query = present_query.filter(AttendanceRecord.student_id.in_(student_scope))
    present_ids = {student_id for (student_id,) in present_query.distinct().all()}
    if present_ids:
        fee_rows = db.query(FeeRecord).filter(
            FeeRecord.student_id.in_(present_ids),
            FeeRecord.is_paid.is_(False),
        ).all()
        due_by_student = {}
        for fee in fee_rows:
            due = max(0.0, float(fee.amount) - float(fee.paid_amount))
            if due <= 0:
                continue
            due_by_student.setdefault(fee.student_id, 0.0)
            due_by_student[fee.student_id] += due
        student_rows = db.query(Student).filter(Student.id.in_(due_by_student.keys())).all()
        for student in student_rows:
            fee_due_present.append(
                {
                    'student_id': student.id,
                    'student_name': student.name,
                    'amount_due': round(due_by_student.get(student.id, 0.0), 2),
                }
            )

    risk_query = db.query(StudentRiskProfile, Student).join(Student, Student.id == StudentRiskProfile.student_id).filter(
        StudentRiskProfile.risk_level == 'HIGH'
    )
    if student_scope:
        risk_query = risk_query.filter(StudentRiskProfile.student_id.in_(student_scope))
    high_risk_students = [
        {
            'student_id': student.id,
            'student_name': student.name,
            'risk_score': profile.final_risk_score,
        }
        for profile, student in risk_query.all()
    ]

    start_window = today - timedelta(days=7)
    absence_query = db.query(
        AttendanceRecord.student_id,
        func.count(AttendanceRecord.id).label('absent_count'),
    ).filter(
        AttendanceRecord.attendance_date >= start_window,
        AttendanceRecord.attendance_date <= today,
        AttendanceRecord.status == 'Absent',
    )
    if student_scope:
        absence_query = absence_query.filter(AttendanceRecord.student_id.in_(student_scope))
    absence_query = absence_query.group_by(AttendanceRecord.student_id).having(func.count(AttendanceRecord.id) >= 2)
    absences = absence_query.all()
    repeat_absentees = []
    if absences:
        absentees_ids = [student_id for student_id, _ in absences]
        student_rows = db.query(Student).filter(Student.id.in_(absentees_ids)).all()
        student_by_id = {student.id: student for student in student_rows}
        for student_id, count in absences:
            student = student_by_id.get(student_id)
            repeat_absentees.append(
                {
                    'student_id': student_id,
                    'student_name': student.name if student else None,
                    'absent_count': int(count),
                }
            )

    return {
        'fee_due_present': fee_due_present,
        'high_risk_students': high_risk_students,
        'repeat_absentees': repeat_absentees,
    }


@timed_service('dashboard_today_view')
def get_today_view(db: Session, *, actor: dict, teacher_filter_id: int | None = None) -> dict:
    role = (actor.get('role') or '').lower()
    user_id = int(actor.get('user_id') or 0)
    teacher_id = None
    if role == 'admin':
        teacher_id = teacher_filter_id
    else:
        teacher_id = user_id

    now = datetime.now()
    today = now.date()
    day_start = datetime.combine(today, time.min)
    day_end = datetime.combine(today, time.max)

    action_query = db.query(PendingAction).filter(
        PendingAction.status == 'open',
        PendingAction.due_at.is_not(None),
    )
    if role != 'admin':
        action_query = action_query.filter(PendingAction.teacher_id == teacher_id)
    elif teacher_id:
        action_query = action_query.filter(PendingAction.teacher_id == teacher_id)

    overdue_rows = (
        action_query.filter(PendingAction.due_at < now)
        .order_by(PendingAction.due_at.asc(), PendingAction.created_at.asc())
        .all()
    )
    due_today_rows = (
        action_query.filter(PendingAction.due_at >= now, PendingAction.due_at <= day_end)
        .order_by(PendingAction.due_at.asc(), PendingAction.created_at.asc())
        .all()
    )

    completed_query = db.query(PendingAction).filter(
        PendingAction.status == 'resolved',
        PendingAction.resolved_at.is_not(None),
        PendingAction.resolved_at >= day_start,
        PendingAction.resolved_at <= day_end,
    )
    if role != 'admin':
        completed_query = completed_query.filter(PendingAction.teacher_id == teacher_id)
    elif teacher_id:
        completed_query = completed_query.filter(PendingAction.teacher_id == teacher_id)
    completed_rows = completed_query.order_by(PendingAction.resolved_at.desc()).all()

    session_ids = {row.session_id or row.related_session_id for row in overdue_rows + due_today_rows + completed_rows if (row.session_id or row.related_session_id)}
    student_ids = {row.student_id for row in overdue_rows + due_today_rows + completed_rows if row.student_id}

    sessions = db.query(ClassSession).filter(ClassSession.id.in_(session_ids)).all() if session_ids else []
    session_map = {row.id: row for row in sessions}
    batch_ids = {row.batch_id for row in sessions}
    batches = db.query(Batch).filter(Batch.id.in_(batch_ids)).all() if batch_ids else []
    batch_map = {row.id: row for row in batches}
    students = db.query(Student).filter(Student.id.in_(student_ids)).all() if student_ids else []
    student_map = {row.id: row for row in students}

    overdue_actions = [_action_payload(db, row, student_map, session_map, batch_map, now, teacher_id) for row in overdue_rows]
    due_today_actions = [_action_payload(db, row, student_map, session_map, batch_map, now, teacher_id) for row in due_today_rows]
    completed_today = [_action_payload(db, row, student_map, session_map, batch_map, now, teacher_id) for row in completed_rows]

    student_scope = None
    batch_scope = None
    if role != 'admin' and teacher_id:
        student_scope = _student_ids_for_teacher(db, teacher_id)
        batch_scope = _teacher_batch_ids(db, teacher_id)
    elif role == 'admin' and teacher_id:
        student_scope = _student_ids_for_teacher(db, teacher_id)
        batch_scope = _teacher_batch_ids(db, teacher_id)

    today_classes = _build_today_classes(db, today=today, now=now, batch_scope=batch_scope, teacher_id=teacher_id)
    flags = _build_flags(db, today=today, student_scope=student_scope)

    payload = {
        'overdue_actions': overdue_actions,
        'due_today_actions': due_today_actions,
        'today_classes': today_classes,
        'flags': flags,
        'completed_today': completed_today,
    }
    return payload
