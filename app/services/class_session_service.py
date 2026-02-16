from datetime import date, datetime, time

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.models import Batch, BatchSchedule, ClassSession
from app.services.time_capacity_service import clear_time_capacity_cache


def _scheduled_datetime_for_batch(batch: Batch, target_date: date) -> datetime:
    hour, minute = 7, 0
    try:
        hh, mm = batch.start_time.split(':', 1)
        hour, minute = int(hh), int(mm)
    except Exception:
        pass
    return datetime.combine(target_date, time(hour=hour, minute=minute))


def _parse_hhmm(value: str) -> time:
    hh, mm = value.split(':', 1)
    hour = int(hh)
    minute = int(mm)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError('Invalid time')
    return time(hour=hour, minute=minute)


def _resolve_schedule_for_date(
    db: Session,
    batch_id: int,
    attendance_date: date,
    scheduled_start: datetime | None,
) -> tuple[datetime | None, int | None]:
    weekday = attendance_date.weekday()
    schedules = (
        db.query(BatchSchedule)
        .filter(BatchSchedule.batch_id == batch_id, BatchSchedule.weekday == weekday)
        .order_by(BatchSchedule.start_time.asc(), BatchSchedule.id.asc())
        .all()
    )
    if not schedules:
        return scheduled_start, None

    if scheduled_start:
        requested_minutes = scheduled_start.hour * 60 + scheduled_start.minute
        matched = None
        best_gap = None
        for row in schedules:
            row_time = _parse_hhmm(row.start_time)
            row_minutes = row_time.hour * 60 + row_time.minute
            gap = abs(requested_minutes - row_minutes)
            if best_gap is None or gap < best_gap:
                matched = row
                best_gap = gap
        if matched:
            row_time = _parse_hhmm(matched.start_time)
            return datetime.combine(attendance_date, row_time), matched.duration_minutes

    row = schedules[0]
    row_time = _parse_hhmm(row.start_time)
    return datetime.combine(attendance_date, row_time), row.duration_minutes


def create_class_session(
    db: Session,
    batch_id: int,
    subject: str,
    scheduled_start: datetime,
    teacher_id: int,
    topic_planned: str = '',
    duration_minutes: int = 60,
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    center_id = int(batch.center_id or 1) if batch else 1
    row = ClassSession(
        batch_id=batch_id,
        subject=subject,
        scheduled_start=scheduled_start,
        duration_minutes=duration_minutes,
        topic_planned=topic_planned,
        teacher_id=teacher_id,
        center_id=center_id,
        status='scheduled',
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    clear_time_capacity_cache()
    return row


def get_session(db: Session, session_id: int):
    return db.query(ClassSession).filter(ClassSession.id == session_id).first()


def list_batch_sessions(db: Session, batch_id: int, limit: int = 30):
    return db.query(ClassSession).filter(ClassSession.batch_id == batch_id).order_by(ClassSession.scheduled_start.desc()).limit(limit).all()


def start_class_session(
    db: Session,
    session_id: int,
    *,
    time_provider: TimeProvider = default_time_provider,
):
    row = get_session(db, session_id)
    if not row:
        raise ValueError('Class session not found')
    if row.status in ('closed', 'missed'):
        raise ValueError('Class session is closed')
    row.status = 'open'
    row.actual_start = row.actual_start or time_provider.now().replace(tzinfo=None)
    db.commit()
    db.refresh(row)
    clear_time_capacity_cache()
    return row


def complete_class_session(
    db: Session,
    session_id: int,
    topic_completed: str = '',
    *,
    time_provider: TimeProvider = default_time_provider,
):
    row = get_session(db, session_id)
    if not row:
        raise ValueError('Class session not found')
    row.status = 'submitted'
    row.actual_start = row.actual_start or time_provider.now().replace(tzinfo=None)
    if topic_completed:
        row.topic_completed = topic_completed
    db.commit()
    db.refresh(row)
    clear_time_capacity_cache()
    return row


def get_or_create_session_for_attendance(
    db: Session,
    batch_id: int,
    attendance_date: date,
    subject: str,
    teacher_id: int,
    scheduled_start: datetime | None,
    topic_planned: str,
    topic_completed: str,
    time_provider: TimeProvider = default_time_provider,
):
    resolved_scheduled_start, resolved_duration = _resolve_schedule_for_date(
        db=db,
        batch_id=batch_id,
        attendance_date=attendance_date,
        scheduled_start=scheduled_start,
    )

    existing_query = db.query(ClassSession).filter(
        ClassSession.batch_id == batch_id,
        func.date(ClassSession.scheduled_start) == attendance_date,
    )
    existing = None
    if resolved_scheduled_start:
        existing = existing_query.filter(ClassSession.scheduled_start == resolved_scheduled_start).first()
    if not existing:
        existing = existing_query.order_by(ClassSession.scheduled_start.asc(), ClassSession.id.asc()).first()

    if existing:
        existing.subject = subject or existing.subject
        existing.teacher_id = teacher_id or existing.teacher_id
        existing.topic_planned = topic_planned or existing.topic_planned
        existing.topic_completed = topic_completed or existing.topic_completed
        if resolved_duration:
            existing.duration_minutes = resolved_duration
        if resolved_scheduled_start:
            existing.scheduled_start = resolved_scheduled_start
        existing.status = 'submitted'
        existing.actual_start = existing.actual_start or time_provider.now().replace(tzinfo=None)
        db.flush()
        db.refresh(existing)
        clear_time_capacity_cache()
        return existing

    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise ValueError('Batch not found')

    row = ClassSession(
        batch_id=batch_id,
        subject=subject or 'General',
        scheduled_start=resolved_scheduled_start or _scheduled_datetime_for_batch(batch, attendance_date),
        duration_minutes=resolved_duration or 60,
        actual_start=time_provider.now().replace(tzinfo=None),
        topic_planned=topic_planned,
        topic_completed=topic_completed,
        teacher_id=teacher_id,
        center_id=int(batch.center_id or 1),
        status='submitted',
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    clear_time_capacity_cache()
    return row


def reopen_session(db: Session, session_id: int, admin_only: bool = True):
    row = get_session(db, session_id)
    if not row:
        raise ValueError('Class session not found')
    _ = admin_only  # Hook for future role-based enforcement in API layer.
    if row.status in ('closed', 'missed', 'submitted', 'completed'):
        row.status = 'open'
        row.closed_at = None
        db.commit()
        db.refresh(row)
        clear_time_capacity_cache()
    return row
