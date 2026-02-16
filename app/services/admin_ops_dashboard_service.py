from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.cache import cache
from app.core.time_provider import TimeProvider, default_time_provider
from app.models import (
    AttendanceRecord,
    AuthUser,
    Batch,
    BatchSchedule,
    ClassSession,
    CommunicationLog,
    FeeRecord,
    PendingAction,
    Student,
    StudentRiskEvent,
    StudentRiskProfile,
)
from app.metrics import timed_service


logger = logging.getLogger(__name__)

_OVERDUE_ALERT_HOURS = 24
_SCHEDULER_IDLE_HOURS = 12
_ATTENDANCE_WINDOW_DAYS = 7
_LOW_ATTENDANCE_WINDOW_DAYS = 30
_LOW_ATTENDANCE_THRESHOLD = 0.75
_LOW_ATTENDANCE_MIN_RECORDS = 3

_AUTOMATION_JOBS = [
    {
        'key': 'post_class_automation',
        'label': 'Post-class automation',
        'notification_type': 'post_class_summary',
        'expected_window_hours': 12,
    },
    {
        'key': 'inbox_escalation',
        'label': 'Inbox escalation job',
        'notification_type': 'inbox_escalation',
        'expected_window_hours': 1,
    },
    {
        'key': 'student_daily_digest',
        'label': 'Student daily digest',
        'notification_type': 'student_daily_digest',
        'expected_window_hours': 36,
    },
    {
        'key': 'homework_reminders',
        'label': 'Homework reminders',
        'notification_type': 'homework_due_reminder',
        'expected_window_hours': 36,
    },
]


def clear_admin_ops_cache() -> None:
    cache.invalidate_prefix('admin_ops')


def _warn_missing_center_filter(*, query_name: str) -> None:
    logger.warning('center_filter_missing service=admin_ops_dashboard query=%s', query_name)


def _last_comm_log(db: Session, notification_type: str) -> datetime | None:
    _warn_missing_center_filter(query_name='communication_log_last_comm')
    return (
        db.query(func.max(CommunicationLog.created_at))
        .filter(CommunicationLog.notification_type == notification_type)
        .scalar()
    )


def _build_system_alerts(db: Session, now: datetime, *, center_id: int) -> list[dict]:
    alerts: list[dict] = []

    overdue_cutoff = now - timedelta(hours=_OVERDUE_ALERT_HOURS)
    overdue_rows = (
        db.query(PendingAction)
        .filter(
            PendingAction.status == 'open',
            PendingAction.due_at.is_not(None),
            PendingAction.due_at < overdue_cutoff,
            PendingAction.center_id == center_id,
        )
        .all()
    )
    if overdue_rows:
        teacher_ids = {row.teacher_id for row in overdue_rows if row.teacher_id}
        oldest_due = min((row.due_at for row in overdue_rows if row.due_at), default=None)
        oldest_hours = None
        if oldest_due:
            oldest_hours = round((now - oldest_due).total_seconds() / 3600.0, 1)
        alerts.append(
            {
                'id': 'overdue_actions',
                'level': 'critical',
                'message': f"{len(overdue_rows)} actions overdue across {len(teacher_ids)} teachers.",
                'count': len(overdue_rows),
                'teacher_count': len(teacher_ids),
                'oldest_overdue_hours': oldest_hours,
                'action_url': '/today',
            }
        )

    yesterday = (now - timedelta(days=1)).date()
    gaps = _attendance_gaps_for_day(db, target_date=yesterday, center_id=center_id)
    if gaps:
        sample = ', '.join([g['batch_name'] for g in gaps[:3]])
        suffix = '...' if len(gaps) > 3 else ''
        alerts.append(
            {
                'id': 'attendance_missing',
                'level': 'critical',
                'message': f"Attendance not submitted yesterday for {len(gaps)} batches ({sample}{suffix}).",
                'count': len(gaps),
                'batches': gaps[:8],
                'action_url': '/attendance',
            }
        )

    _warn_missing_center_filter(query_name='communication_log_failures')
    failure_since = now - timedelta(hours=24)
    failed_rows = (
        db.query(
            CommunicationLog.notification_type,
            func.count(CommunicationLog.id).label('fail_count'),
        )
        .filter(
            CommunicationLog.status == 'failed',
            CommunicationLog.notification_type.in_([job['notification_type'] for job in _AUTOMATION_JOBS]),
            CommunicationLog.created_at >= failure_since,
        )
        .group_by(CommunicationLog.notification_type)
        .all()
    )
    for notification_type, fail_count in failed_rows:
        alerts.append(
            {
                'id': f'automation_failed_{notification_type}',
                'level': 'warning',
                'message': f"{int(fail_count)} {notification_type} notifications failed in the last 24 hours.",
                'count': int(fail_count),
                'notification_type': notification_type,
                'action_url': '/settings',
            }
        )

    latest_activity = max(
        (row for row in (_last_comm_log(db, job['notification_type']) for job in _AUTOMATION_JOBS) if row),
        default=None,
    )
    if not latest_activity or (now - latest_activity) > timedelta(hours=_SCHEDULER_IDLE_HOURS):
        alerts.append(
            {
                'id': 'scheduler_idle',
                'level': 'warning',
                'message': f"No automation activity logged in the last {_SCHEDULER_IDLE_HOURS} hours.",
                'action_url': '/admin/ops',
            }
        )

    return alerts


def _attendance_gaps_for_day(db: Session, *, target_date: date, center_id: int) -> list[dict]:
    weekday = target_date.weekday()
    schedules = (
        db.query(BatchSchedule, Batch)
        .join(Batch, Batch.id == BatchSchedule.batch_id)
        .filter(BatchSchedule.weekday == weekday, Batch.active.is_(True), Batch.center_id == center_id)
        .all()
    )
    if not schedules:
        return []

    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date, time.max)
    batch_ids = {batch.id for _, batch in schedules}
    sessions = (
        db.query(ClassSession)
        .filter(
            ClassSession.batch_id.in_(batch_ids),
            ClassSession.scheduled_start >= day_start,
            ClassSession.scheduled_start <= day_end,
            ClassSession.center_id == center_id,
        )
        .all()
    )
    by_key = {(session.batch_id, session.scheduled_start): session for session in sessions}
    gaps = []
    for schedule, batch in schedules:
        start_dt = datetime.combine(target_date, datetime.strptime(schedule.start_time, '%H:%M').time())
        session = by_key.get((batch.id, start_dt))
        if session and session.status in ('submitted', 'closed'):
            continue
        gaps.append(
            {
                'batch_id': batch.id,
                'batch_name': batch.name,
                'scheduled_start': start_dt.isoformat(),
                'status': session.status if session else 'missing',
            }
        )
    return gaps


def _build_teacher_bottlenecks(db: Session, now: datetime, *, center_id: int) -> list[dict]:
    open_actions = (
        db.query(PendingAction)
        .filter(PendingAction.status == 'open', PendingAction.teacher_id.is_not(None), PendingAction.center_id == center_id)
        .all()
    )
    overdue_by_teacher: dict[int, list[PendingAction]] = {}
    open_by_teacher: dict[int, list[PendingAction]] = {}
    for row in open_actions:
        if not row.teacher_id:
            continue
        open_by_teacher.setdefault(row.teacher_id, []).append(row)
        if row.due_at and row.due_at < now:
            overdue_by_teacher.setdefault(row.teacher_id, []).append(row)

    yesterday = (now - timedelta(days=1)).date()
    day_start = datetime.combine(yesterday, time.min)
    day_end = datetime.combine(yesterday, time.max)
    missed_sessions = (
        db.query(ClassSession.teacher_id, func.count(ClassSession.id))
        .filter(
            ClassSession.teacher_id.is_not(None),
            ClassSession.scheduled_start >= day_start,
            ClassSession.scheduled_start <= day_end,
            ClassSession.status.not_in(['submitted', 'closed']),
            ClassSession.center_id == center_id,
        )
        .group_by(ClassSession.teacher_id)
        .all()
    )
    missed_by_teacher = {int(teacher_id): int(count) for teacher_id, count in missed_sessions if teacher_id}

    teacher_ids = set(open_by_teacher.keys()) | set(missed_by_teacher.keys())
    if not teacher_ids:
        return []

    teachers = db.query(AuthUser).filter(AuthUser.id.in_(teacher_ids), AuthUser.center_id == center_id).all()
    teacher_map = {row.id: row for row in teachers}

    payload = []
    for teacher_id in teacher_ids:
        open_rows = open_by_teacher.get(teacher_id, [])
        overdue_rows = overdue_by_teacher.get(teacher_id, [])
        oldest_due = min((row.due_at for row in overdue_rows if row.due_at), default=None)
        oldest_hours = None
        if oldest_due:
            oldest_hours = round((now - oldest_due).total_seconds() / 3600.0, 1)
        teacher = teacher_map.get(teacher_id)
        payload.append(
            {
                'teacher_id': teacher_id,
                'teacher_label': f"Teacher {teacher_id}",
                'teacher_phone': teacher.phone if teacher else None,
                'open_actions': len(open_rows),
                'overdue_actions': len(overdue_rows),
                'oldest_overdue_hours': oldest_hours,
                'classes_missed': missed_by_teacher.get(teacher_id, 0),
            }
        )
    payload.sort(key=lambda row: (-row['overdue_actions'], -row['open_actions'], row['teacher_id']))
    return payload


def _build_batch_health(db: Session, now: datetime, *, center_id: int) -> list[dict]:
    active_batches = db.query(Batch).filter(Batch.active.is_(True), Batch.center_id == center_id).all()
    if not active_batches:
        return []

    batch_ids = [batch.id for batch in active_batches]
    schedules = db.query(BatchSchedule).filter(BatchSchedule.batch_id.in_(batch_ids)).all()
    schedule_by_batch: dict[int, list[BatchSchedule]] = {}
    for schedule in schedules:
        schedule_by_batch.setdefault(schedule.batch_id, []).append(schedule)

    end_date = now.date()
    start_date = end_date - timedelta(days=_ATTENDANCE_WINDOW_DAYS - 1)
    date_span = [start_date + timedelta(days=offset) for offset in range(_ATTENDANCE_WINDOW_DAYS)]

    expected_by_batch: dict[int, int] = {batch_id: 0 for batch_id in batch_ids}
    for batch_id, rows in schedule_by_batch.items():
        if not rows:
            continue
        for schedule in rows:
            for day in date_span:
                if schedule.weekday == day.weekday():
                    expected_by_batch[batch_id] += 1

    sessions = (
        db.query(ClassSession.batch_id, ClassSession.status, ClassSession.scheduled_start)
        .filter(
            ClassSession.batch_id.in_(batch_ids),
            ClassSession.scheduled_start >= datetime.combine(start_date, time.min),
            ClassSession.scheduled_start <= datetime.combine(end_date, time.max),
            ClassSession.center_id == center_id,
        )
        .all()
    )
    completed_by_batch: dict[int, int] = {batch_id: 0 for batch_id in batch_ids}
    last_class_by_batch: dict[int, datetime] = {}
    for batch_id, status, scheduled_start in sessions:
        if status in ('submitted', 'closed'):
            completed_by_batch[batch_id] += 1
        if scheduled_start and (batch_id not in last_class_by_batch or scheduled_start > last_class_by_batch[batch_id]):
            last_class_by_batch[batch_id] = scheduled_start

    recent_absent = _absent_counts_by_batch(db, start_date, end_date, center_id=center_id)
    prev_start = start_date - timedelta(days=_ATTENDANCE_WINDOW_DAYS)
    prev_end = start_date - timedelta(days=1)
    previous_absent = _absent_counts_by_batch(db, prev_start, prev_end, center_id=center_id)

    fee_due = (
        db.query(Student.batch_id, func.count(func.distinct(FeeRecord.student_id)))
        .join(Student, Student.id == FeeRecord.student_id)
        .filter(
            Student.batch_id.in_(batch_ids),
            Student.center_id == center_id,
            FeeRecord.is_paid.is_(False),
            (FeeRecord.amount - FeeRecord.paid_amount) > 0,
        )
        .group_by(Student.batch_id)
        .all()
    )
    fee_due_by_batch = {int(batch_id): int(count) for batch_id, count in fee_due}

    repeat_absentees = _repeat_absentees_by_batch(db, start_date, end_date, center_id=center_id)

    payload = []
    for batch in active_batches:
        expected = expected_by_batch.get(batch.id, 0)
        completed = completed_by_batch.get(batch.id, 0)
        completion_rate = None
        if expected:
            completion_rate = round((completed / expected) * 100.0, 1)
        recent_absent_count = recent_absent.get(batch.id, 0)
        prev_absent_count = previous_absent.get(batch.id, 0)
        trend = 'flat'
        if recent_absent_count > prev_absent_count:
            trend = 'up'
        elif recent_absent_count < prev_absent_count:
            trend = 'down'

        flags = []
        if completion_rate is not None and completion_rate < 75:
            flags.append('falling_attendance')
        if trend == 'up' and recent_absent_count >= 3:
            flags.append('absences_rising')
        if repeat_absentees.get(batch.id, 0) >= 2:
            flags.append('repeat_no_shows')

        payload.append(
            {
                'batch_id': batch.id,
                'batch_name': batch.name,
                'attendance_completion_rate': completion_rate,
                'absentee_trend': trend,
                'recent_absent_count': recent_absent_count,
                'fee_due_students': fee_due_by_batch.get(batch.id, 0),
                'last_class_date': last_class_by_batch.get(batch.id).isoformat() if last_class_by_batch.get(batch.id) else None,
                'repeat_no_show_students': repeat_absentees.get(batch.id, 0),
                'attention_flags': flags,
            }
        )

    payload.sort(key=lambda row: (row['attendance_completion_rate'] is None, row['attendance_completion_rate'] or 0))
    return payload


def _absent_counts_by_batch(db: Session, start: date, end: date, *, center_id: int) -> dict[int, int]:
    rows = (
        db.query(Student.batch_id, func.count(AttendanceRecord.id))
        .join(AttendanceRecord, AttendanceRecord.student_id == Student.id)
        .filter(
            AttendanceRecord.attendance_date >= start,
            AttendanceRecord.attendance_date <= end,
            AttendanceRecord.status == 'Absent',
            Student.center_id == center_id,
        )
        .group_by(Student.batch_id)
        .all()
    )
    return {int(batch_id): int(count) for batch_id, count in rows if batch_id is not None}


def _repeat_absentees_by_batch(db: Session, start: date, end: date, *, center_id: int) -> dict[int, int]:
    subquery = (
        db.query(
            Student.id.label('student_id'),
            Student.batch_id.label('batch_id'),
            func.count(AttendanceRecord.id).label('absent_count'),
        )
        .join(AttendanceRecord, AttendanceRecord.student_id == Student.id)
        .filter(
            AttendanceRecord.attendance_date >= start,
            AttendanceRecord.attendance_date <= end,
            AttendanceRecord.status == 'Absent',
            Student.center_id == center_id,
        )
        .group_by(Student.id, Student.batch_id)
        .having(func.count(AttendanceRecord.id) >= 2)
        .subquery()
    )
    rows = db.query(subquery.c.batch_id, func.count(subquery.c.student_id)).group_by(subquery.c.batch_id).all()
    return {int(batch_id): int(count) for batch_id, count in rows if batch_id is not None}


def _build_student_risk_summary(db: Session, now: datetime, *, center_id: int) -> dict:
    high_risk = (
        db.query(StudentRiskProfile)
        .join(Student, Student.id == StudentRiskProfile.student_id)
        .filter(StudentRiskProfile.risk_level == 'HIGH', Student.center_id == center_id)
        .count()
    )
    week_start = now - timedelta(days=7)
    new_risks = (
        db.query(StudentRiskEvent)
        .join(Student, Student.id == StudentRiskEvent.student_id)
        .filter(StudentRiskEvent.created_at >= week_start, Student.center_id == center_id)
        .count()
    )

    attendance_start = now.date() - timedelta(days=_LOW_ATTENDANCE_WINDOW_DAYS)
    attendance_rows = (
        db.query(
            AttendanceRecord.student_id,
            func.count(AttendanceRecord.id).label('total'),
            func.sum(case((AttendanceRecord.status == 'Present', 1), else_=0)).label('present'),
        )
        .join(Student, Student.id == AttendanceRecord.student_id)
        .filter(
            AttendanceRecord.attendance_date >= attendance_start,
            AttendanceRecord.attendance_date <= now.date(),
            Student.center_id == center_id,
        )
        .group_by(AttendanceRecord.student_id)
        .all()
    )
    low_attendance = 0
    for _, total, present in attendance_rows:
        total_count = int(total or 0)
        if total_count < _LOW_ATTENDANCE_MIN_RECORDS:
            continue
        present_count = int(present or 0)
        if total_count and (present_count / total_count) < _LOW_ATTENDANCE_THRESHOLD:
            low_attendance += 1

    return {
        'high_risk_students': int(high_risk),
        'new_risk_entries_week': int(new_risks),
        'low_attendance_students': int(low_attendance),
        'attendance_threshold_percent': int(_LOW_ATTENDANCE_THRESHOLD * 100),
        'attendance_window_days': _LOW_ATTENDANCE_WINDOW_DAYS,
    }


def _build_automation_health(db: Session, now: datetime) -> dict:
    _warn_missing_center_filter(query_name='communication_log_automation_health')
    items = []
    for job in _AUTOMATION_JOBS:
        last_run = _last_comm_log(db, job['notification_type'])
        status = 'missing'
        age_hours = None
        if last_run:
            age_hours = round((now - last_run).total_seconds() / 3600.0, 1)
            status = 'ok' if age_hours <= job['expected_window_hours'] else 'stale'
        items.append(
            {
                'key': job['key'],
                'label': job['label'],
                'notification_type': job['notification_type'],
                'last_run_at': last_run.isoformat() if last_run else None,
                'age_hours': age_hours,
                'expected_window_hours': job['expected_window_hours'],
                'status': status,
            }
        )
    return {'items': items}


@timed_service('admin_ops_dashboard')
def get_admin_ops_dashboard(
    db: Session,
    *,
    center_id: int,
    now: datetime | None = None,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    center_id = int(center_id or 0)
    if center_id <= 0:
        raise ValueError('center_id is required')
    now = now or time_provider.now().replace(tzinfo=None)
    payload = {
        'system_alerts': [],
        'teacher_bottlenecks': [],
        'batch_health': [],
        'student_risk_summary': {},
        'automation_health': {},
        'generated_at': now.isoformat(),
    }

    try:
        payload['system_alerts'] = _build_system_alerts(db, now, center_id=center_id)
    except Exception:
        logger.exception('admin_ops_system_alerts_failed')

    try:
        payload['teacher_bottlenecks'] = _build_teacher_bottlenecks(db, now, center_id=center_id)
    except Exception:
        logger.exception('admin_ops_teacher_bottlenecks_failed')

    try:
        payload['batch_health'] = _build_batch_health(db, now, center_id=center_id)
    except Exception:
        logger.exception('admin_ops_batch_health_failed')

    try:
        payload['student_risk_summary'] = _build_student_risk_summary(db, now, center_id=center_id)
    except Exception:
        logger.exception('admin_ops_student_risk_failed')

    try:
        payload['automation_health'] = _build_automation_health(db, now)
    except Exception:
        logger.exception('admin_ops_automation_failed')

    return payload
