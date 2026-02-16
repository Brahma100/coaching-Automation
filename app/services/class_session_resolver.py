from __future__ import annotations

import logging
from datetime import date, datetime, time

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.models import Batch, BatchSchedule, CalendarOverride, ClassSession


logger = logging.getLogger(__name__)


def _parse_hhmm(value: str) -> time:
    hh, mm = (value or '').split(':', 1)
    hour = int(hh)
    minute = int(mm)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError('Invalid time')
    return time(hour=hour, minute=minute)


def _resolve_slot(batch: Batch, schedule: BatchSchedule | None, target_date: date) -> tuple[datetime, int]:
    if schedule:
        slot_time = _parse_hhmm(schedule.start_time)
        return datetime.combine(target_date, slot_time), schedule.duration_minutes
    try:
        slot_time = _parse_hhmm(batch.start_time)
    except Exception:
        slot_time = time(hour=7, minute=0)
    return datetime.combine(target_date, slot_time), 60


def is_session_locked(session: ClassSession) -> bool:
    return session.status in ('submitted', 'closed', 'missed', 'completed')


def resolve_or_create_class_session(
    db: Session,
    batch_id: int,
    schedule_id: int | None,
    target_date: date,
    source: str = 'web',
    teacher_id: int = 0,
    time_provider: TimeProvider = default_time_provider,
) -> tuple[ClassSession, bool]:
    if source not in ('telegram', 'web', 'system'):
        raise ValueError('source must be telegram, web, or system')

    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise ValueError('Batch not found')

    schedule = None
    override = (
        db.query(CalendarOverride)
        .filter(
            CalendarOverride.batch_id == batch_id,
            CalendarOverride.override_date == target_date,
        )
        .order_by(CalendarOverride.id.desc())
        .first()
    )
    if override and override.cancelled:
        raise ValueError('Class is cancelled for this date')

    # Explicit negative schedule ids reference override rows from attendance options.
    if schedule_id and int(schedule_id) < 0:
        override_id = abs(int(schedule_id))
        override = (
            db.query(CalendarOverride)
            .filter(
                CalendarOverride.id == override_id,
                CalendarOverride.batch_id == batch_id,
                CalendarOverride.override_date == target_date,
                CalendarOverride.cancelled.is_(False),
            )
            .first()
        )
        if not override or not override.new_start_time:
            raise ValueError('Schedule not found for this batch')
    elif not (override and override.new_start_time):
        # No usable override selected/found: fall back to normal schedule resolution.
        if schedule_id:
            schedule = (
                db.query(BatchSchedule)
                .filter(
                    BatchSchedule.id == schedule_id,
                    BatchSchedule.batch_id == batch_id,
                )
                .first()
            )
            if not schedule:
                raise ValueError('Schedule not found for this batch')

    if override is not None:
        slot_time = _parse_hhmm(str(override.new_start_time))
        scheduled_start = datetime.combine(target_date, slot_time)
        duration_minutes = int(override.new_duration_minutes or 60)
    else:
        scheduled_start, duration_minutes = _resolve_slot(batch, schedule, target_date)
    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date, time.max)

    existing = (
        db.query(ClassSession)
        .filter(
            and_(
                ClassSession.batch_id == batch_id,
                ClassSession.scheduled_start >= day_start,
                ClassSession.scheduled_start <= day_end,
                ClassSession.scheduled_start == scheduled_start,
            )
        )
        .first()
    )

    if existing:
        if teacher_id and not existing.teacher_id:
            existing.teacher_id = teacher_id
        if duration_minutes:
            existing.duration_minutes = duration_minutes
        if not existing.subject:
            existing.subject = batch.subject or 'General'
        db.commit()
        db.refresh(existing)
        logger.info(
            'class_session_resolved_existing batch_id=%s session_id=%s source=%s',
            batch_id,
            existing.id,
            source,
        )
        return existing, is_session_locked(existing)

    row = ClassSession(
        batch_id=batch_id,
        subject=batch.subject or 'General',
        scheduled_start=scheduled_start,
        duration_minutes=duration_minutes,
        actual_start=time_provider.now().replace(tzinfo=None),
        teacher_id=teacher_id or 0,
        center_id=int(batch.center_id or 1),
        status='open',
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(
        'class_session_created batch_id=%s session_id=%s source=%s',
        batch_id,
        row.id,
        source,
    )
    return row, False
