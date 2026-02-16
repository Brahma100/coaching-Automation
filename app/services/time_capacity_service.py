from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.cache import cache, cache_key
from app.core.time_provider import TimeProvider, default_time_provider
from app.models import AuthUser, Batch, BatchSchedule, CalendarOverride, ClassSession, StudentBatchMap, TeacherUnavailability
from app.services.access_scope_service import get_teacher_batch_ids
from app.services.center_scope_service import get_current_center_id


TIME_CAPACITY_TTL_SECONDS = 30
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Interval:
    start: datetime
    end: datetime
    slot_type: str
    source: str
    slot_id: int | str | None = None
    batch_id: int | None = None
    room_id: int | None = None
    reason: str = ''


def _default_work_window() -> tuple[time, time]:
    return time(hour=7, minute=0), time(hour=20, minute=0)


def _teacher_work_window(db: Session, teacher_id: int) -> tuple[time, time, int]:
    start_time, end_time = _default_work_window()
    snap = 15
    user = db.query(AuthUser).filter(AuthUser.id == teacher_id).first()
    if not user:
        return start_time, end_time, snap
    start_time = user.daily_work_start_time or start_time
    end_time = user.daily_work_end_time or end_time
    snap = max(5, min(60, int(user.calendar_snap_minutes or 15)))
    return start_time, end_time, snap


def _to_datetime(day: date, value: time) -> datetime:
    return datetime.combine(day, value)


def _parse_hhmm(value: str) -> time:
    hh, mm = value.split(':', 1)
    hour = int(hh)
    minute = int(mm)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError('Invalid HH:MM time')
    return time(hour=hour, minute=minute)


def _round_to_snap(dt: datetime, snap_minutes: int) -> datetime:
    minute = (dt.minute // snap_minutes) * snap_minutes
    return dt.replace(minute=minute, second=0, microsecond=0)


def _normalize_interval(interval: _Interval, *, range_start: datetime, range_end: datetime) -> _Interval | None:
    start = max(interval.start, range_start)
    end = min(interval.end, range_end)
    if end <= start:
        return None
    return _Interval(
        start=start,
        end=end,
        slot_type=interval.slot_type,
        source=interval.source,
        slot_id=interval.slot_id,
        batch_id=interval.batch_id,
        room_id=interval.room_id,
        reason=interval.reason,
    )


def _merge_intervals(intervals: list[_Interval], *, range_start: datetime, range_end: datetime) -> list[_Interval]:
    normalized = [
        row
        for row in (
            _normalize_interval(interval, range_start=range_start, range_end=range_end)
            for interval in intervals
        )
        if row is not None
    ]
    if not normalized:
        return []
    normalized.sort(key=lambda row: (row.start, row.end))
    merged: list[_Interval] = [normalized[0]]
    for current in normalized[1:]:
        last = merged[-1]
        if current.start <= last.end:
            merged[-1] = _Interval(
                start=last.start,
                end=max(last.end, current.end),
                slot_type=last.slot_type if last.slot_type == current.slot_type else 'busy',
                source=last.source if last.source == current.source else 'mixed',
                slot_id=last.slot_id if last.slot_id == current.slot_id else None,
                batch_id=last.batch_id if last.batch_id == current.batch_id else None,
                room_id=last.room_id if last.room_id == current.room_id else None,
                reason=last.reason or current.reason,
            )
            continue
        merged.append(current)
    return merged


def _subtract_intervals(
    *,
    range_start: datetime,
    range_end: datetime,
    busy_intervals: list[_Interval],
) -> list[_Interval]:
    if range_end <= range_start:
        return []
    merged_busy = _merge_intervals(busy_intervals, range_start=range_start, range_end=range_end)
    free: list[_Interval] = []
    cursor = range_start
    for row in merged_busy:
        if row.start > cursor:
            free.append(
                _Interval(
                    start=cursor,
                    end=row.start,
                    slot_type='free',
                    source='derived',
                )
            )
        if row.end > cursor:
            cursor = row.end
    if cursor < range_end:
        free.append(
            _Interval(
                start=cursor,
                end=range_end,
                slot_type='free',
                source='derived',
            )
        )
    return free


def _interval_minutes(row: _Interval) -> int:
    return max(0, int((row.end - row.start).total_seconds() // 60))


def _serialize_interval(row: _Interval) -> dict[str, Any]:
    return {
        'start': row.start.isoformat(),
        'end': row.end.isoformat(),
        'start_time': row.start.strftime('%H:%M'),
        'end_time': row.end.strftime('%H:%M'),
        'minutes': _interval_minutes(row),
        'type': row.slot_type,
        'source': row.source,
        'id': row.slot_id,
        'batch_id': row.batch_id,
        'room_id': row.room_id,
        'reason': row.reason or '',
    }


def _current_center_id_or_raise(*, query_name: str) -> int:
    center_id = int(get_current_center_id() or 0)
    if center_id <= 0:
        logger.warning('center_filter_missing service=time_capacity query=%s', query_name)
        raise ValueError('center_id is required')
    return center_id


def _resolve_teacher_batch_ids(db: Session, teacher_id: int) -> set[int]:
    center_id = _current_center_id_or_raise(query_name='resolve_teacher_batch_ids')
    if int(teacher_id or 0) <= 0:
        return {
            int(batch_id)
            for (batch_id,) in (
                db.query(BatchSchedule.batch_id)
                .join(Batch, Batch.id == BatchSchedule.batch_id)
                .filter(Batch.active.is_(True), Batch.center_id == center_id)
                .distinct()
                .all()
            )
            if batch_id is not None
        }
    return get_teacher_batch_ids(db, int(teacher_id), center_id=center_id)


def _collect_schedule_occurrences_for_day(
    db: Session,
    *,
    teacher_id: int,
    target_date: date,
) -> list[_Interval]:
    teacher_batch_ids = _resolve_teacher_batch_ids(db, teacher_id)
    if not teacher_batch_ids:
        return []

    weekday = target_date.weekday()
    schedules = (
        db.query(BatchSchedule)
        .options(selectinload(BatchSchedule.batch))
        .filter(
            BatchSchedule.batch_id.in_(teacher_batch_ids),
            BatchSchedule.weekday == weekday,
        )
        .all()
    )
    if not schedules:
        return []

    overrides = (
        db.query(CalendarOverride)
        .filter(
            CalendarOverride.batch_id.in_(teacher_batch_ids),
            CalendarOverride.override_date == target_date,
        )
        .all()
    )
    override_by_batch = {row.batch_id: row for row in overrides}

    items: list[_Interval] = []
    for schedule in schedules:
        override = override_by_batch.get(schedule.batch_id)
        if override and override.cancelled:
            continue

        start_clock = _parse_hhmm(schedule.start_time)
        duration = int(schedule.duration_minutes or 60)
        reason = ''
        if override and override.new_start_time:
            start_clock = _parse_hhmm(override.new_start_time)
            duration = int(override.new_duration_minutes or duration)
            reason = (override.reason or '').strip()
        elif override and override.new_duration_minutes:
            duration = int(override.new_duration_minutes or duration)
            reason = (override.reason or '').strip()
        start_dt = datetime.combine(target_date, start_clock)
        end_dt = start_dt + timedelta(minutes=duration)
        room_id = schedule.batch.room_id if schedule.batch else None
        items.append(
            _Interval(
                start=start_dt,
                end=end_dt,
                slot_type='busy',
            source='schedule',
            slot_id=f'schedule:{schedule.batch_id}:{start_dt.isoformat()}',
            batch_id=schedule.batch_id,
            room_id=room_id,
            reason=reason,
            )
        )
    return items


def _collect_class_sessions_for_day(
    db: Session,
    *,
    teacher_id: int,
    target_date: date,
    teacher_batch_ids: set[int],
) -> list[_Interval]:
    center_id = _current_center_id_or_raise(query_name='collect_class_sessions_for_day')
    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date, time.max)

    query = (
        db.query(ClassSession, Batch.room_id)
        .outerjoin(Batch, Batch.id == ClassSession.batch_id)
        .filter(
            ClassSession.scheduled_start >= day_start,
            ClassSession.scheduled_start <= day_end,
            ClassSession.center_id == center_id,
        )
    )
    if teacher_batch_ids:
        query = query.filter(ClassSession.batch_id.in_(teacher_batch_ids))
    if teacher_id:
        query = query.filter(or_(ClassSession.teacher_id == teacher_id, ClassSession.teacher_id == 0))
    rows = query.all()
    return [
        _Interval(
            start=session.scheduled_start,
            end=session.scheduled_start + timedelta(minutes=int(session.duration_minutes or 60)),
            slot_type='busy',
            source='class_session',
            slot_id=session.id,
            batch_id=session.batch_id,
            room_id=room_id,
            reason='',
        )
        for session, room_id in rows
        if session.scheduled_start is not None
    ]


def _collect_teacher_unavailability_for_day(db: Session, *, teacher_id: int, target_date: date) -> list[_Interval]:
    rows = (
        db.query(TeacherUnavailability)
        .filter(
            TeacherUnavailability.teacher_id == teacher_id,
            TeacherUnavailability.date == target_date,
        )
        .order_by(TeacherUnavailability.start_time.asc(), TeacherUnavailability.id.asc())
        .all()
    )
    return [
        _Interval(
            start=datetime.combine(row.date, row.start_time),
            end=datetime.combine(row.date, row.end_time),
            slot_type='blocked',
            source='teacher_block',
            slot_id=row.id,
            batch_id=None,
            room_id=None,
            reason=(row.reason or '').strip(),
        )
        for row in rows
        if row.end_time > row.start_time
    ]


def _availability_cache_key(teacher_id: int, target_date: date, actor_user_id: int | None = None) -> str:
    return cache_key('time_capacity:availability', f'{int(actor_user_id or 0)}:{teacher_id}:{target_date.isoformat()}')


def _batch_capacity_cache_key(actor_user_id: int | None = None, teacher_id: int | None = None) -> str:
    return cache_key('time_capacity:batch_capacity', f'{int(actor_user_id or 0)}:{int(teacher_id or 0)}')


def _reschedule_cache_key(teacher_id: int, batch_id: int, target_date: date, actor_user_id: int | None = None) -> str:
    return cache_key('time_capacity:reschedule', f'{int(actor_user_id or 0)}:{teacher_id}:{batch_id}:{target_date.isoformat()}')


def _weekly_load_cache_key(teacher_id: int, week_start: date, actor_user_id: int | None = None) -> str:
    return cache_key('time_capacity:weekly_load', f'{int(actor_user_id or 0)}:{teacher_id}:{week_start.isoformat()}')


def clear_time_capacity_cache() -> None:
    cache.invalidate_prefix('time_capacity:')


def _collect_busy_intervals_for_day(db: Session, *, teacher_id: int, target_date: date) -> list[_Interval]:
    teacher_batch_ids = _resolve_teacher_batch_ids(db, teacher_id)
    schedule_rows = _collect_schedule_occurrences_for_day(db, teacher_id=teacher_id, target_date=target_date)
    session_rows = _collect_class_sessions_for_day(
        db,
        teacher_id=teacher_id,
        target_date=target_date,
        teacher_batch_ids=teacher_batch_ids,
    )
    blocked_rows = _collect_teacher_unavailability_for_day(db, teacher_id=teacher_id, target_date=target_date)
    return [*schedule_rows, *session_rows, *blocked_rows]


def get_teacher_availability(
    db: Session,
    teacher_id: int,
    target_date: date,
    *,
    actor_user_id: int | None = None,
    time_provider: TimeProvider = default_time_provider,
) -> dict[str, Any]:
    key = _availability_cache_key(teacher_id, target_date, actor_user_id=actor_user_id)
    cached = cache.get_cached(key)
    if cached is not None:
        return cached

    work_start, work_end, snap_minutes = _teacher_work_window(db, teacher_id)
    range_start = _round_to_snap(_to_datetime(target_date, work_start), snap_minutes)
    range_end = _to_datetime(target_date, work_end).replace(second=0, microsecond=0)
    if range_end <= range_start:
        range_end = range_start + timedelta(hours=1)

    busy_rows = _collect_busy_intervals_for_day(db, teacher_id=teacher_id, target_date=target_date)
    free_rows = _subtract_intervals(range_start=range_start, range_end=range_end, busy_intervals=busy_rows)
    merged_busy = _merge_intervals(busy_rows, range_start=range_start, range_end=range_end)
    total_busy_minutes = sum(_interval_minutes(row) for row in merged_busy)
    total_free_minutes = sum(_interval_minutes(row) for row in free_rows)
    payload = {
        'teacher_id': int(teacher_id),
        'date': target_date.isoformat(),
        'snap_minutes': snap_minutes,
        'work_window': {
            'start_time': range_start.strftime('%H:%M'),
            'end_time': range_end.strftime('%H:%M'),
        },
        'busy_slots': [_serialize_interval(row) for row in merged_busy],
        'free_slots': [_serialize_interval(row) for row in free_rows],
        'total_busy_minutes': total_busy_minutes,
        'total_free_minutes': total_free_minutes,
    }
    cache.set_cached(key, payload, ttl=TIME_CAPACITY_TTL_SECONDS)
    return payload


def get_batch_capacity(
    db: Session,
    *,
    actor_role: str = 'admin',
    actor_user_id: int | None = None,
) -> list[dict[str, Any]]:
    center_id = _current_center_id_or_raise(query_name='get_batch_capacity')
    scoped_teacher_id = int(actor_user_id or 0) if (actor_role or '').strip().lower() == 'teacher' else 0
    key = _batch_capacity_cache_key(actor_user_id=actor_user_id, teacher_id=scoped_teacher_id)
    cached = cache.get_cached(key)
    if cached is not None:
        return cached

    batch_query = db.query(Batch).filter(Batch.active.is_(True), Batch.center_id == center_id)
    if scoped_teacher_id > 0:
        scoped_batch_ids = _resolve_teacher_batch_ids(db, scoped_teacher_id)
        if not scoped_batch_ids:
            cache.set_cached(key, [], ttl=TIME_CAPACITY_TTL_SECONDS)
            return []
        batch_query = batch_query.filter(Batch.id.in_(scoped_batch_ids))
    rows = batch_query.order_by(Batch.name.asc()).all()
    batch_ids = [row.id for row in rows]
    enrolled_counts: dict[int, int] = {}
    if batch_ids:
        enrolled_counts = {
            int(batch_id): int(count)
            for batch_id, count in (
                db.query(StudentBatchMap.batch_id, func.count(func.distinct(StudentBatchMap.student_id)))
                .join(Batch, Batch.id == StudentBatchMap.batch_id)
                .filter(
                    StudentBatchMap.batch_id.in_(batch_ids),
                    StudentBatchMap.active.is_(True),
                    Batch.center_id == center_id,
                )
                .group_by(StudentBatchMap.batch_id)
                .all()
            )
        }

    payload = []
    for batch in rows:
        enrolled = int(enrolled_counts.get(batch.id, 0))
        max_students = int(batch.max_students) if batch.max_students is not None else None
        available_seats = (max_students - enrolled) if max_students is not None else None
        utilization = 0.0
        if max_students and max_students > 0:
            utilization = round((enrolled / max_students) * 100.0, 2)
        payload.append(
            {
                'batch_id': batch.id,
                'name': batch.name,
                'max_students': max_students,
                'enrolled_students': enrolled,
                'available_seats': available_seats,
                'utilization_percentage': utilization,
            }
        )

    cache.set_cached(key, payload, ttl=TIME_CAPACITY_TTL_SECONDS)
    return payload


def _default_duration_for_batch(batch: Batch, target_date: date) -> int:
    duration = int(batch.default_duration_minutes or 60)
    for schedule in batch.schedules:
        if schedule.weekday == target_date.weekday():
            return int(schedule.duration_minutes or duration)
    return duration


def _room_conflicts_for_day(
    db: Session,
    *,
    room_id: int,
    target_date: date,
    excluding_batch_id: int,
) -> list[_Interval]:
    center_id = _current_center_id_or_raise(query_name='room_conflicts_for_day')
    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date, time.max)
    batch_ids = [
        int(batch_id)
        for (batch_id,) in db.query(Batch.id).filter(Batch.room_id == room_id, Batch.id != excluding_batch_id, Batch.center_id == center_id).all()
    ]
    if not batch_ids:
        return []

    session_rows = (
        db.query(ClassSession)
        .filter(
            ClassSession.batch_id.in_(batch_ids),
            ClassSession.scheduled_start >= day_start,
            ClassSession.scheduled_start <= day_end,
            ClassSession.center_id == center_id,
        )
        .all()
    )
    schedule_rows = (
        db.query(BatchSchedule)
        .filter(
            BatchSchedule.batch_id.in_(batch_ids),
            BatchSchedule.weekday == target_date.weekday(),
        )
        .all()
    )
    override_rows = (
        db.query(CalendarOverride)
        .filter(
            CalendarOverride.batch_id.in_(batch_ids),
            CalendarOverride.override_date == target_date,
        )
        .all()
    )
    override_by_batch = {row.batch_id: row for row in override_rows}

    intervals: list[_Interval] = []
    for session in session_rows:
        start_dt = session.scheduled_start
        end_dt = start_dt + timedelta(minutes=int(session.duration_minutes or 60))
        intervals.append(
            _Interval(
                start=start_dt,
                end=end_dt,
                slot_type='busy',
                source='room_class_session',
                slot_id=session.id,
                batch_id=session.batch_id,
                room_id=room_id,
            )
        )

    for schedule in schedule_rows:
        override = override_by_batch.get(schedule.batch_id)
        if override and override.cancelled:
            continue
        start_clock = _parse_hhmm(schedule.start_time)
        duration = int(schedule.duration_minutes or 60)
        if override and override.new_start_time:
            start_clock = _parse_hhmm(override.new_start_time)
            duration = int(override.new_duration_minutes or duration)
        elif override and override.new_duration_minutes:
            duration = int(override.new_duration_minutes or duration)
        start_dt = datetime.combine(target_date, start_clock)
        end_dt = start_dt + timedelta(minutes=duration)
        intervals.append(
            _Interval(
                start=start_dt,
                end=end_dt,
                slot_type='busy',
                source='room_schedule',
                slot_id=f'room_schedule:{schedule.batch_id}:{start_dt.isoformat()}',
                batch_id=schedule.batch_id,
                room_id=room_id,
            )
        )
    return intervals


def get_reschedule_options(
    db: Session,
    teacher_id: int,
    batch_id: int,
    target_date: date,
    *,
    actor_user_id: int | None = None,
    time_provider: TimeProvider = default_time_provider,
) -> list[dict[str, Any]]:
    center_id = _current_center_id_or_raise(query_name='get_reschedule_options')
    key = _reschedule_cache_key(teacher_id, batch_id, target_date, actor_user_id=actor_user_id)
    cached = cache.get_cached(key)
    if cached is not None:
        return cached

    batch = (
        db.query(Batch)
        .options(selectinload(Batch.schedules))
        .filter(Batch.id == batch_id, Batch.active.is_(True), Batch.center_id == center_id)
        .first()
    )
    if not batch:
        raise ValueError('Batch not found')
    if int(teacher_id or 0) > 0:
        teacher_batch_ids = _resolve_teacher_batch_ids(db, int(teacher_id))
        if not teacher_batch_ids:
            return []
        if int(batch_id) not in teacher_batch_ids:
            return []

    options: list[dict[str, Any]] = []
    now_cutoff = time_provider.now().replace(tzinfo=None)
    work_start, work_end, snap_minutes = _teacher_work_window(db, teacher_id)
    for day_offset in range(0, 7):
        day = target_date + timedelta(days=day_offset)
        availability = get_teacher_availability(
            db,
            teacher_id,
            day,
            actor_user_id=actor_user_id,
            time_provider=time_provider,
        )
        duration_minutes = _default_duration_for_batch(batch, day)

        free_slots = availability.get('free_slots', [])
        day_load = int(availability.get('total_busy_minutes') or 0)
        room_conflicts: list[_Interval] = []
        if batch.room_id:
            room_conflicts = _room_conflicts_for_day(
                db,
                room_id=batch.room_id,
                target_date=day,
                excluding_batch_id=batch.id,
            )
        merged_room_conflicts = _merge_intervals(
            room_conflicts,
            range_start=datetime.combine(day, work_start),
            range_end=datetime.combine(day, work_end),
        )

        for free in free_slots:
            free_start = datetime.fromisoformat(free['start'])
            free_end = datetime.fromisoformat(free['end'])
            candidate_start = _round_to_snap(free_start, snap_minutes)
            while candidate_start + timedelta(minutes=duration_minutes) <= free_end:
                candidate_end = candidate_start + timedelta(minutes=duration_minutes)
                if candidate_start <= now_cutoff:
                    candidate_start += timedelta(minutes=snap_minutes)
                    continue
                has_room_conflict = any(
                    candidate_start < conflict.end and conflict.start < candidate_end
                    for conflict in merged_room_conflicts
                )
                if not has_room_conflict:
                    options.append(
                        {
                            'date': day.isoformat(),
                            'start': candidate_start.isoformat(),
                            'end': candidate_end.isoformat(),
                            'start_time': candidate_start.strftime('%H:%M'),
                            'end_time': candidate_end.strftime('%H:%M'),
                            'duration_minutes': duration_minutes,
                            'batch_id': batch.id,
                            'batch_name': batch.name,
                            'room_id': batch.room_id,
                            'day_busy_minutes': day_load,
                        }
                    )
                candidate_start += timedelta(minutes=snap_minutes)

    options.sort(key=lambda row: (row['start'], row['day_busy_minutes']))
    if options:
        earliest = options[0]['start']
        min_load = min(row['day_busy_minutes'] for row in options)
        for row in options:
            row['is_best_earliest'] = row['start'] == earliest
            row['is_best_low_load'] = row['day_busy_minutes'] == min_load

    cache.set_cached(key, options, ttl=TIME_CAPACITY_TTL_SECONDS)
    return options


def get_weekly_load(
    db: Session,
    teacher_id: int,
    week_start: date,
    *,
    actor_user_id: int | None = None,
    time_provider: TimeProvider = default_time_provider,
) -> dict[str, Any]:
    key = _weekly_load_cache_key(teacher_id, week_start, actor_user_id=actor_user_id)
    cached = cache.get_cached(key)
    if cached is not None:
        return cached

    work_start, work_end, _ = _teacher_work_window(db, teacher_id)
    work_minutes_per_day = max(
        1,
        int((datetime.combine(week_start, work_end) - datetime.combine(week_start, work_start)).total_seconds() // 60),
    )

    daily_rows = []
    total_busy_minutes = 0
    total_free_minutes = 0
    for day_offset in range(0, 7):
        day = week_start + timedelta(days=day_offset)
        availability = get_teacher_availability(
            db,
            teacher_id,
            day,
            actor_user_id=actor_user_id,
            time_provider=time_provider,
        )
        busy_minutes = int(availability.get('total_busy_minutes') or 0)
        free_minutes = int(availability.get('total_free_minutes') or 0)
        total_busy_minutes += busy_minutes
        total_free_minutes += free_minutes
        daily_rows.append(
            {
                'date': day.isoformat(),
                'total_minutes': busy_minutes,
            }
        )

    total_work_minutes = work_minutes_per_day * 7
    utilization = round((total_busy_minutes / total_work_minutes) * 100.0, 2) if total_work_minutes > 0 else 0.0
    free_utilization = round((total_free_minutes / total_work_minutes) * 100.0, 2) if total_work_minutes > 0 else 0.0
    payload = {
        'teacher_id': int(teacher_id),
        'week_start': week_start.isoformat(),
        'work_minutes_per_day': work_minutes_per_day,
        'daily_hours': daily_rows,
        'total_weekly_minutes': total_busy_minutes,
        'utilization_percentage': utilization,
        'free_minutes': total_free_minutes,
        'free_utilization_percentage': free_utilization,
    }
    cache.set_cached(key, payload, ttl=TIME_CAPACITY_TTL_SECONDS)
    return payload


def create_teacher_unavailability(
    db: Session,
    *,
    teacher_id: int,
    target_date: date,
    start_time_value: time,
    end_time_value: time,
    reason: str = '',
) -> TeacherUnavailability:
    if end_time_value <= start_time_value:
        raise ValueError('end_time must be after start_time')

    existing = (
        db.query(TeacherUnavailability)
        .filter(
            TeacherUnavailability.teacher_id == teacher_id,
            TeacherUnavailability.date == target_date,
            TeacherUnavailability.start_time < end_time_value,
            TeacherUnavailability.end_time > start_time_value,
        )
        .first()
    )
    if existing:
        raise ValueError('Block overlaps an existing blocked slot')

    row = TeacherUnavailability(
        teacher_id=teacher_id,
        date=target_date,
        start_time=start_time_value,
        end_time=end_time_value,
        reason=(reason or '').strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    clear_time_capacity_cache()
    return row


def delete_teacher_unavailability(db: Session, *, teacher_id: int, block_id: int, admin: bool = False) -> bool:
    query = db.query(TeacherUnavailability).filter(TeacherUnavailability.id == block_id)
    if not admin:
        query = query.filter(TeacherUnavailability.teacher_id == teacher_id)
    row = query.first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    clear_time_capacity_cache()
    return True
