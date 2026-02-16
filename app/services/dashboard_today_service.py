from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models import (
    AttendanceRecord,
    Batch,
    BatchSchedule,
    CalendarOverride,
    ClassSession,
    FeeRecord,
    PendingAction,
    Student,
    StudentBatchMap,
    StudentRiskProfile,
)
from app.cache import cache
from app.core.time_provider import TimeProvider, default_time_provider
from app.services.access_scope_service import get_teacher_batch_ids
from app.services.center_scope_service import get_actor_center_id
from app.metrics import timed_service


logger = logging.getLogger(__name__)


def clear_today_view_cache() -> None:
    cache.invalidate_prefix('today_view')


def _warn_missing_center_filter(*, query_name: str) -> None:
    logger.warning('center_filter_missing service=dashboard_today query=%s', query_name)


def _student_ids_for_batch_scope(db: Session, batch_ids: set[int] | None, *, center_id: int) -> set[int]:
    if not batch_ids:
        return set()
    rows = (
        db.query(StudentBatchMap.student_id)
        .join(Student, Student.id == StudentBatchMap.student_id)
        .filter(
            StudentBatchMap.batch_id.in_(batch_ids),
            StudentBatchMap.active.is_(True),
            Student.center_id == center_id,
        )
        .distinct()
        .all()
    )
    if rows:
        return {student_id for (student_id,) in rows}
    fallback = db.query(Student.id).filter(Student.batch_id.in_(batch_ids), Student.center_id == center_id).all()
    return {student_id for (student_id,) in fallback}


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
        'needs_token': bool(row.action_type == 'review_session_summary' and session),
        'token_type': 'session_summary' if row.action_type == 'review_session_summary' and session else None,
        'token_entity_id': int(session.id) if row.action_type == 'review_session_summary' and session else None,
        'token_command_endpoint': '/api/commands/generate-token' if row.action_type == 'review_session_summary' and session else None,
        'token_payload': (
            {
                'session_id': int(session.id),
                'teacher_id': int(teacher_id or 0),
                'role': 'teacher',
            }
            if row.action_type == 'review_session_summary' and session
            else None
        ),
        'token_ttl_minutes': 24 * 60 if row.action_type == 'review_session_summary' and session else None,
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
    center_id: int | None = None,
    time_provider: TimeProvider = default_time_provider,
) -> list[dict]:
    weekday = today.weekday()
    schedule_query = (
        db.query(BatchSchedule, Batch)
        .join(Batch, Batch.id == BatchSchedule.batch_id)
        .filter(BatchSchedule.weekday == weekday, Batch.active.is_(True))
        .order_by(BatchSchedule.start_time.asc(), BatchSchedule.id.asc())
    )
    if int(center_id or 0) > 0:
        schedule_query = schedule_query.filter(Batch.center_id == int(center_id))
    if batch_scope:
        schedule_query = schedule_query.filter(BatchSchedule.batch_id.in_(batch_scope))
    schedules = schedule_query.all()
    schedule_batch_ids = {int(batch.id) for _, batch in schedules}

    override_query = (
        db.query(CalendarOverride, Batch)
        .join(Batch, Batch.id == CalendarOverride.batch_id)
        .filter(CalendarOverride.override_date == today, Batch.active.is_(True))
        .order_by(CalendarOverride.id.asc())
    )
    if int(center_id or 0) > 0:
        override_query = override_query.filter(Batch.center_id == int(center_id))
    if batch_scope:
        override_query = override_query.filter(CalendarOverride.batch_id.in_(batch_scope))
    overrides = override_query.all()
    override_by_batch: dict[int, CalendarOverride] = {}
    for override_row, _ in overrides:
        override_by_batch[int(override_row.batch_id)] = override_row

    slot_rows: list[dict] = []
    seen_slot_keys: set[tuple[int, str, int]] = set()
    for schedule, batch in schedules:
        override = override_by_batch.get(int(batch.id))
        if override and override.cancelled:
            continue
        start_time = (override.new_start_time if (override and override.new_start_time) else schedule.start_time) or schedule.start_time
        duration_minutes = int(
            override.new_duration_minutes
            if (override and override.new_duration_minutes)
            else (schedule.duration_minutes or batch.default_duration_minutes or 60)
        )
        slot_key = (int(batch.id), str(start_time), int(duration_minutes))
        if slot_key in seen_slot_keys:
            continue
        seen_slot_keys.add(slot_key)
        slot_rows.append(
            {
                'batch': batch,
                'schedule_id': schedule.id,
                'start_time': start_time,
                'duration_minutes': duration_minutes,
            }
        )

    for override, batch in overrides:
        batch_id = int(batch.id)
        if batch_id in schedule_batch_ids:
            continue
        if override.cancelled or not override.new_start_time:
            continue
        duration_minutes = int(override.new_duration_minutes or batch.default_duration_minutes or 60)
        slot_key = (int(batch.id), str(override.new_start_time), duration_minutes)
        if slot_key in seen_slot_keys:
            continue
        seen_slot_keys.add(slot_key)
        slot_rows.append(
            {
                'batch': batch,
                'schedule_id': None,
                'start_time': override.new_start_time,
                'duration_minutes': duration_minutes,
            }
        )

    if not slot_rows:
        return []

    day_start = datetime.combine(today, time.min)
    day_end = datetime.combine(today, time.max)
    batch_ids = {int(row['batch'].id) for row in slot_rows}
    sessions = (
        db.query(ClassSession)
        .filter(
            ClassSession.batch_id.in_(batch_ids),
            ClassSession.scheduled_start >= day_start,
            ClassSession.scheduled_start <= day_end,
            ClassSession.center_id == int(center_id),
        )
        .all()
    )
    by_key = {(s.batch_id, s.scheduled_start): s for s in sessions}
    payload = []
    for row in slot_rows:
        batch = row['batch']
        schedule_id = row['schedule_id']
        start_clock = str(row['start_time'] or '')
        start_time = datetime.combine(today, datetime.strptime(start_clock, '%H:%M').time())
        session = by_key.get((int(batch.id), start_time))
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
        attendance_token_ttl_minutes = None
        if session:
            end_time = session.scheduled_start + timedelta(minutes=session.duration_minutes or 60)
            attendance_token_ttl_minutes = int(
                max(1, (end_time + timedelta(minutes=10) - time_provider.now().replace(tzinfo=None)).total_seconds() // 60)
            )

        payload.append(
            {
                'batch_id': batch.id,
                'batch_name': batch.name,
                'schedule_id': schedule_id,
                'session_id': session.id if session else None,
                'scheduled_start': start_time.isoformat(),
                'duration_minutes': int(row['duration_minutes'] or 60),
                'attendance_status': status_label,
                'attendance_url': attendance_url,
                'summary_url': summary_url,
                'needs_attendance_token': bool(session),
                'attendance_token_type': 'attendance_open' if session else None,
                'attendance_token_ttl_minutes': attendance_token_ttl_minutes,
                'attendance_token_command_endpoint': '/api/commands/generate-token' if session else None,
                'attendance_token_payload': (
                    {
                        'session_id': int(session.id),
                        'batch_id': int(batch.id),
                        'schedule_id': schedule_id,
                        'teacher_id': int(teacher_id or 0),
                        'role': 'teacher',
                    }
                    if session
                    else None
                ),
                'needs_summary_token': bool(session),
                'summary_token_type': 'session_summary' if session else None,
                'summary_token_ttl_minutes': 24 * 60 if session else None,
                'summary_token_command_endpoint': '/api/commands/generate-token' if session else None,
                'summary_token_payload': (
                    {'session_id': int(session.id), 'teacher_id': int(teacher_id or 0), 'role': 'teacher'}
                    if session
                    else None
                ),
            }
        )
    return payload


def _build_flags(db: Session, *, today: date, student_scope: set[int] | None, center_id: int) -> dict:
    fee_due_present = []
    present_query = db.query(AttendanceRecord.student_id).join(Student, Student.id == AttendanceRecord.student_id).filter(
        AttendanceRecord.attendance_date == today,
        AttendanceRecord.status == 'Present',
        Student.center_id == center_id,
    )
    if student_scope:
        present_query = present_query.filter(AttendanceRecord.student_id.in_(student_scope))
    present_ids = {student_id for (student_id,) in present_query.distinct().all()}
    if present_ids:
        fee_rows = db.query(FeeRecord).join(Student, Student.id == FeeRecord.student_id).filter(
            FeeRecord.student_id.in_(present_ids),
            FeeRecord.is_paid.is_(False),
            Student.center_id == center_id,
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
        StudentRiskProfile.risk_level == 'HIGH',
        Student.center_id == center_id,
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
    ).join(Student, Student.id == AttendanceRecord.student_id).filter(
        AttendanceRecord.attendance_date >= start_window,
        AttendanceRecord.attendance_date <= today,
        AttendanceRecord.status == 'Absent',
        Student.center_id == center_id,
    )
    if student_scope:
        absence_query = absence_query.filter(AttendanceRecord.student_id.in_(student_scope))
    absence_query = absence_query.group_by(AttendanceRecord.student_id).having(func.count(AttendanceRecord.id) >= 2)
    absences = absence_query.all()
    repeat_absentees = []
    if absences:
        absentees_ids = [student_id for student_id, _ in absences]
        student_rows = db.query(Student).filter(Student.id.in_(absentees_ids), Student.center_id == center_id).all()
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
def get_today_view(
    db: Session,
    *,
    actor: dict,
    teacher_filter_id: int | None = None,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    role = (actor.get('role') or '').lower()
    user_id = int(actor.get('user_id') or 0)
    center_id = int(get_actor_center_id(actor) or 0)
    if center_id <= 0:
        _warn_missing_center_filter(query_name='get_today_view_missing_center_id')
        return {
            'overdue_actions': [],
            'due_today_actions': [],
            'today_classes': [],
            'flags': {'fee_due_present': [], 'high_risk_students': [], 'repeat_absentees': []},
            'completed_today': [],
        }
    teacher_id = int(teacher_filter_id or 0) if role == 'admin' else user_id
    batch_scope: set[int] | None = None
    if role == 'teacher':
        batch_scope = get_teacher_batch_ids(db, teacher_id, center_id=center_id)
        if not batch_scope:
            return {
                'overdue_actions': [],
                'due_today_actions': [],
                'today_classes': [],
                'flags': {'fee_due_present': [], 'high_risk_students': [], 'repeat_absentees': []},
                'completed_today': [],
            }
    elif role == 'admin' and teacher_id > 0:
        batch_scope = get_teacher_batch_ids(db, teacher_id, center_id=center_id)
        if not batch_scope:
            return {
                'overdue_actions': [],
                'due_today_actions': [],
                'today_classes': [],
                'flags': {'fee_due_present': [], 'high_risk_students': [], 'repeat_absentees': []},
                'completed_today': [],
            }

    now = time_provider.now().replace(tzinfo=None)
    today = now.date()
    day_start = datetime.combine(today, time.min)
    day_end = datetime.combine(today, time.max)

    action_query = db.query(PendingAction).filter(
        PendingAction.status == 'open',
        PendingAction.due_at.is_not(None),
        PendingAction.center_id == center_id,
    )
    if role == 'teacher':
        action_query = action_query.filter(PendingAction.teacher_id == teacher_id)
    elif role == 'admin' and teacher_id:
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
        PendingAction.center_id == center_id,
    )
    if role == 'teacher':
        completed_query = completed_query.filter(PendingAction.teacher_id == teacher_id)
    elif role == 'admin' and teacher_id:
        completed_query = completed_query.filter(PendingAction.teacher_id == teacher_id)
    completed_rows = completed_query.order_by(PendingAction.resolved_at.desc()).all()

    session_ids = {row.session_id or row.related_session_id for row in overdue_rows + due_today_rows + completed_rows if (row.session_id or row.related_session_id)}
    student_ids = {row.student_id for row in overdue_rows + due_today_rows + completed_rows if row.student_id}

    sessions = (
        db.query(ClassSession)
        .filter(ClassSession.id.in_(session_ids), ClassSession.center_id == center_id)
        .all()
        if session_ids
        else []
    )
    session_map = {row.id: row for row in sessions}
    batch_ids = {row.batch_id for row in sessions}
    batches = (
        db.query(Batch)
        .filter(Batch.id.in_(batch_ids), Batch.center_id == center_id)
        .all()
        if batch_ids
        else []
    )
    batch_map = {row.id: row for row in batches}
    students = (
        db.query(Student)
        .filter(Student.id.in_(student_ids), Student.center_id == center_id)
        .all()
        if student_ids
        else []
    )
    student_map = {row.id: row for row in students}

    def _action_allowed(row: PendingAction) -> bool:
        if not batch_scope:
            return True
        session_ref_id = row.session_id or row.related_session_id
        if session_ref_id:
            session_ref = session_map.get(session_ref_id)
            if not session_ref:
                return False
            return int(session_ref.batch_id or 0) in batch_scope
        if row.student_id:
            student_ref = student_map.get(row.student_id)
            if not student_ref:
                return False
            return int(student_ref.batch_id or 0) in batch_scope
        return False

    scoped_overdue_rows = [row for row in overdue_rows if _action_allowed(row)]
    scoped_due_today_rows = [row for row in due_today_rows if _action_allowed(row)]
    scoped_completed_rows = [row for row in completed_rows if _action_allowed(row)]

    overdue_actions = [_action_payload(db, row, student_map, session_map, batch_map, now, teacher_id or None) for row in scoped_overdue_rows]
    due_today_actions = [_action_payload(db, row, student_map, session_map, batch_map, now, teacher_id or None) for row in scoped_due_today_rows]
    completed_today = [_action_payload(db, row, student_map, session_map, batch_map, now, teacher_id or None) for row in scoped_completed_rows]

    student_scope = _student_ids_for_batch_scope(db, batch_scope, center_id=center_id) if batch_scope else None

    today_classes = _build_today_classes(
        db,
        today=today,
        now=now,
        batch_scope=batch_scope,
        teacher_id=teacher_id,
        center_id=center_id,
        time_provider=time_provider,
    )
    flags = _build_flags(db, today=today, student_scope=student_scope, center_id=center_id)

    payload = {
        'overdue_actions': overdue_actions,
        'due_today_actions': due_today_actions,
        'today_classes': today_classes,
        'flags': flags,
        'completed_today': completed_today,
    }
    return payload
