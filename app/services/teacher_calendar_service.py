from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
import json

import httpx
from sqlalchemy import case, func
from sqlalchemy.orm import Session, selectinload

from app.cache import cache, cache_key
from app.models import AttendanceRecord, AuthUser, Batch, BatchSchedule, CalendarHoliday, CalendarOverride, ClassSession, FeeRecord, Room, Student, StudentBatchMap, StudentRiskProfile


CALENDAR_TTL_SECONDS = 60
VALID_VIEWS = {'day', 'week', 'month', 'agenda'}
NAGER_HOLIDAY_URL = 'https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code}'


@dataclass(frozen=True)
class _Occurrence:
    batch_id: int
    start_dt: datetime
    end_dt: datetime
    duration_minutes: int


def _parse_start_minutes(start_time: str) -> int:
    hh, mm = start_time.split(':', 1)
    hour = int(hh)
    minute = int(mm)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError('start_time must be HH:MM')
    return hour * 60 + minute


def _parse_time(start_time: str) -> time:
    _parse_start_minutes(start_time)
    return datetime.strptime(start_time, '%H:%M').time()


def _window_for_day(day: date) -> tuple[datetime, datetime]:
    return datetime.combine(day, time.min), datetime.combine(day, time.max)


def _calendar_cache_key(
    *,
    role: str,
    actor_user_id: int | None,
    teacher_id: int,
    start_date: date,
    end_date: date,
    view: str,
) -> str:
    scope = f"{role}:{int(actor_user_id or 0)}"
    identity = f"{scope}:teacher:{teacher_id}:{start_date.isoformat()}:{end_date.isoformat()}:{view}"
    return cache_key('teacher_calendar', identity)


def _apply_overrides(
    *,
    occurrences: list[_Occurrence],
    overrides: list[CalendarOverride],
) -> list[_Occurrence]:
    by_day: dict[tuple[int, date], list[_Occurrence]] = {}
    for item in occurrences:
        by_day.setdefault((item.batch_id, item.start_dt.date()), []).append(item)

    for override in sorted(overrides, key=lambda row: (row.override_date, row.id)):
        key = (override.batch_id, override.override_date)
        existing = by_day.get(key, [])
        if override.cancelled:
            by_day[key] = []
            continue

        if existing:
            updated_rows: list[_Occurrence] = []
            for current in existing:
                new_start = current.start_dt
                if override.new_start_time:
                    new_start = datetime.combine(override.override_date, _parse_time(override.new_start_time))
                duration = int(override.new_duration_minutes or current.duration_minutes)
                new_end = new_start + timedelta(minutes=duration)
                updated_rows.append(
                    _Occurrence(
                        batch_id=current.batch_id,
                        start_dt=new_start,
                        end_dt=new_end,
                        duration_minutes=duration,
                    )
                )
            by_day[key] = updated_rows
            continue

        if not override.new_start_time:
            continue
        duration = int(override.new_duration_minutes or 60)
        start_dt = datetime.combine(override.override_date, _parse_time(override.new_start_time))
        by_day.setdefault(key, []).append(
            _Occurrence(
                batch_id=override.batch_id,
                start_dt=start_dt,
                end_dt=start_dt + timedelta(minutes=duration),
                duration_minutes=duration,
            )
        )

    payload: list[_Occurrence] = []
    for rows in by_day.values():
        payload.extend(rows)
    payload.sort(key=lambda row: (row.start_dt, row.batch_id))
    return payload


def _expand_recurring_occurrences(
    schedules: list[BatchSchedule],
    *,
    start_date: date,
    end_date: date,
) -> list[_Occurrence]:
    items: list[_Occurrence] = []
    day = start_date
    while day <= end_date:
        weekday = day.weekday()
        for schedule in schedules:
            if schedule.weekday != weekday:
                continue
            start_dt = datetime.combine(day, _parse_time(schedule.start_time))
            duration = int(schedule.duration_minutes or 60)
            items.append(
                _Occurrence(
                    batch_id=schedule.batch_id,
                    start_dt=start_dt,
                    end_dt=start_dt + timedelta(minutes=duration),
                    duration_minutes=duration,
                )
            )
        day += timedelta(days=1)
    items.sort(key=lambda row: (row.start_dt, row.batch_id))
    return items


def _session_status_label(
    *,
    now: datetime,
    start_dt: datetime,
    end_dt: datetime,
    session: ClassSession | None,
) -> tuple[str, str]:
    if session and session.status == 'cancelled':
        return 'cancelled', 'cancelled'
    if session and session.status == 'missed':
        return 'completed', 'pending'

    if session and session.status in ('submitted', 'closed'):
        return 'completed', 'submitted'

    live = start_dt <= now < end_dt
    if live:
        attendance_status = 'open' if session else 'pending'
        return 'live', attendance_status

    if now >= end_dt:
        if session and session.status in ('open', 'running'):
            return 'completed', 'pending'
        return 'completed', 'pending'

    return 'upcoming', 'not_started'


def _find_best_session(
    *,
    sessions: list[ClassSession],
    start_dt: datetime,
) -> ClassSession | None:
    if not sessions:
        return None
    exact = [row for row in sessions if row.scheduled_start == start_dt]
    if exact:
        return sorted(exact, key=lambda row: row.id, reverse=True)[0]

    nearest = sorted(
        sessions,
        key=lambda row: (abs((row.scheduled_start - start_dt).total_seconds()), -row.id),
    )
    candidate = nearest[0]
    if abs((candidate.scheduled_start - start_dt).total_seconds()) <= 60 * 45:
        return candidate
    return None


def get_teacher_calendar_view(
    db: Session,
    teacher_id: int,
    start_date: date,
    end_date: date,
    view: str,
    *,
    actor_role: str = 'teacher',
    actor_user_id: int | None = None,
    bypass_cache: bool = False,
) -> list[dict[str, Any]]:
    clean_view = (view or '').strip().lower()
    if clean_view not in VALID_VIEWS:
        raise ValueError('view must be one of: day, week, month, agenda')
    if end_date < start_date:
        raise ValueError('end_date must be greater than or equal to start_date')

    cache_token = _calendar_cache_key(
        role=(actor_role or 'teacher').lower(),
        actor_user_id=actor_user_id,
        teacher_id=int(teacher_id),
        start_date=start_date,
        end_date=end_date,
        view=clean_view,
    )
    if not bypass_cache:
        cached = cache.get_cached(cache_token)
        if cached is not None:
            return cached

    day_start, _ = _window_for_day(start_date)
    _, day_end = _window_for_day(end_date)

    schedules = (
        db.query(BatchSchedule)
        .options(selectinload(BatchSchedule.batch))
        .join(Batch, Batch.id == BatchSchedule.batch_id)
        .filter(Batch.active.is_(True))
        .order_by(BatchSchedule.weekday.asc(), BatchSchedule.start_time.asc(), BatchSchedule.id.asc())
        .all()
    )

    if not schedules:
        payload: list[dict[str, Any]] = []
        cache.set_cached(cache_token, payload, ttl=CALENDAR_TTL_SECONDS)
        return payload

    batch_map: dict[int, Batch] = {row.batch_id: row.batch for row in schedules if row.batch is not None}
    batch_ids = sorted(batch_map.keys())
    room_ids = {batch.room_id for batch in batch_map.values() if batch.room_id}
    rooms = db.query(Room).filter(Room.id.in_(room_ids)).all() if room_ids else []
    room_map = {room.id: room for room in rooms}

    occurrences = _expand_recurring_occurrences(schedules, start_date=start_date, end_date=end_date)

    overrides = (
        db.query(CalendarOverride)
        .filter(
            CalendarOverride.batch_id.in_(batch_ids),
            CalendarOverride.override_date >= start_date,
            CalendarOverride.override_date <= end_date,
        )
        .order_by(CalendarOverride.override_date.asc(), CalendarOverride.id.asc())
        .all()
    )
    occurrences = _apply_overrides(occurrences=occurrences, overrides=overrides)

    session_query = db.query(ClassSession).filter(
        ClassSession.batch_id.in_(batch_ids),
        ClassSession.scheduled_start >= day_start - timedelta(hours=1),
        ClassSession.scheduled_start <= day_end + timedelta(hours=1),
    )
    if teacher_id:
        session_query = session_query.filter(ClassSession.teacher_id == teacher_id)
    sessions = session_query.order_by(ClassSession.scheduled_start.asc(), ClassSession.id.asc()).all()
    sessions_by_batch: dict[int, list[ClassSession]] = {}
    for row in sessions:
        sessions_by_batch.setdefault(row.batch_id, []).append(row)

    active_student_counts = {
        int(batch_id): int(count)
        for batch_id, count in (
            db.query(StudentBatchMap.batch_id, func.count(func.distinct(StudentBatchMap.student_id)))
            .filter(
                StudentBatchMap.batch_id.in_(batch_ids),
                StudentBatchMap.active.is_(True),
            )
            .group_by(StudentBatchMap.batch_id)
            .all()
        )
    }

    fee_due_counts_by_batch = {
        int(batch_id): int(count)
        for batch_id, count in (
            db.query(StudentBatchMap.batch_id, func.count(func.distinct(FeeRecord.student_id)))
            .join(FeeRecord, FeeRecord.student_id == StudentBatchMap.student_id)
            .filter(
                StudentBatchMap.batch_id.in_(batch_ids),
                StudentBatchMap.active.is_(True),
                FeeRecord.is_paid.is_(False),
                FeeRecord.due_date <= end_date,
            )
            .group_by(StudentBatchMap.batch_id)
            .all()
        )
    }

    risk_counts_by_batch = {
        int(batch_id): int(count)
        for batch_id, count in (
            db.query(StudentBatchMap.batch_id, func.count(func.distinct(StudentRiskProfile.student_id)))
            .join(StudentRiskProfile, StudentRiskProfile.student_id == StudentBatchMap.student_id)
            .filter(
                StudentBatchMap.batch_id.in_(batch_ids),
                StudentBatchMap.active.is_(True),
                StudentRiskProfile.risk_level == 'HIGH',
            )
            .group_by(StudentBatchMap.batch_id)
            .all()
        )
    }

    now = datetime.now()
    payload: list[dict[str, Any]] = []
    for occurrence in occurrences:
        batch = batch_map.get(occurrence.batch_id)
        if not batch:
            continue

        session = _find_best_session(
            sessions=sessions_by_batch.get(occurrence.batch_id, []),
            start_dt=occurrence.start_dt,
        )
        end_dt = occurrence.start_dt + timedelta(minutes=occurrence.duration_minutes)
        status, attendance_status = _session_status_label(
            now=now,
            start_dt=occurrence.start_dt,
            end_dt=end_dt,
            session=session,
        )
        fee_due_count = int(fee_due_counts_by_batch.get(occurrence.batch_id, 0))
        risk_count = int(risk_counts_by_batch.get(occurrence.batch_id, 0))

        room = room_map.get(batch.room_id) if batch.room_id else None
        payload.append(
            {
                'session_id': session.id if session else None,
                'batch_id': occurrence.batch_id,
                'batch_name': batch.name,
                'subject': (session.subject if session and session.subject else batch.subject) or 'General',
                'academic_level': batch.academic_level,
                'room_id': batch.room_id,
                'room': room.name if room else None,
                'location': batch.location,
                'is_online': batch.is_online,
                'meeting_link': batch.meeting_link,
                'max_students': batch.max_students,
                'start_datetime': occurrence.start_dt.isoformat(),
                'end_datetime': end_dt.isoformat(),
                'student_count': int(active_student_counts.get(occurrence.batch_id, 0)),
                'fee_due_count': fee_due_count,
                'risk_count': risk_count,
                'status': status,
                'live_status': status == 'live',
                'attendance_status': attendance_status,
                'duration_minutes': int(occurrence.duration_minutes),
                'color_code': batch.color_code,
                'conflict_score': 0,
                'flags': {
                    'has_overdue_fees': fee_due_count > 0,
                    'has_high_risk_students': risk_count > 0,
                },
            }
        )

    _apply_conflict_scores(payload)

    cache.set_cached(cache_token, payload, ttl=CALENDAR_TTL_SECONDS)
    return payload


def _apply_conflict_scores(items: list[dict[str, Any]]) -> None:
    def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
        return a_start < b_end and b_start < a_end

    parsed = []
    for item in items:
        parsed.append(
            (
                item,
                datetime.fromisoformat(item['start_datetime']),
                datetime.fromisoformat(item['end_datetime']),
                item.get('room_id'),
            )
        )

    for idx, (item, start_a, end_a, room_a) in enumerate(parsed):
        conflicts = 0
        for jdx, (other, start_b, end_b, room_b) in enumerate(parsed):
            if idx == jdx:
                continue
            if overlaps(start_a, end_a, start_b, end_b):
                if room_a and room_a == room_b:
                    conflicts += 1
        item['conflict_score'] = conflicts


def _fetch_public_holidays(country_code: str, year: int) -> list[dict[str, Any]]:
    try:
        response = httpx.get(
            NAGER_HOLIDAY_URL.format(year=year, country_code=country_code),
            timeout=12.0,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            rows = [row for row in payload if isinstance(row, dict)]
            if rows:
                return rows
    except Exception:
        pass

    try:
        import holidays as pyholidays

        holiday_items = pyholidays.country_holidays(country_code, years=[year])
        return [
            {
                'date': holiday_date.isoformat(),
                'name': name,
                'localName': name,
                'global': True,
            }
            for holiday_date, name in holiday_items.items()
        ]
    except Exception:
        return []


def sync_calendar_holidays(
    db: Session,
    *,
    country_code: str = 'IN',
    start_year: int | None = None,
    years: int = 5,
) -> dict[str, Any]:
    clean_country = (country_code or 'IN').upper().strip()
    if len(clean_country) != 2:
        raise ValueError('country_code must be a 2-letter ISO country code')

    clean_years = int(years or 0)
    if clean_years < 1 or clean_years > 10:
        raise ValueError('years must be between 1 and 10')

    base_year = int(start_year or date.today().year)
    fetched_years: list[int] = []
    total_rows = 0

    for year in range(base_year, base_year + clean_years):
        rows = _fetch_public_holidays(clean_country, year)

        db.query(CalendarHoliday).filter(
            CalendarHoliday.country_code == clean_country,
            CalendarHoliday.year == year,
        ).delete(synchronize_session=False)

        mapped_rows: list[CalendarHoliday] = []
        seen = set()
        for row in rows:
            raw_date = row.get('date')
            raw_name = (row.get('name') or '').strip()
            if not raw_date or not raw_name:
                continue
            try:
                holiday_date = date.fromisoformat(str(raw_date))
            except ValueError:
                continue

            dedupe_key = (holiday_date, raw_name.lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            mapped_rows.append(
                CalendarHoliday(
                    country_code=clean_country,
                    holiday_date=holiday_date,
                    year=holiday_date.year,
                    name=raw_name,
                    local_name=(row.get('localName') or raw_name).strip(),
                    source='nager',
                    is_national=bool(row.get('global', True)),
                )
            )

        if mapped_rows:
            db.add_all(mapped_rows)
            total_rows += len(mapped_rows)
        fetched_years.append(year)

    db.commit()
    clear_teacher_calendar_cache()
    return {
        'country_code': clean_country,
        'start_year': base_year,
        'years': clean_years,
        'fetched_years': fetched_years,
        'total_rows': total_rows,
    }


def get_calendar_holidays(
    db: Session,
    *,
    start_date: date,
    end_date: date,
    country_code: str = 'IN',
) -> list[dict[str, Any]]:
    clean_country = (country_code or 'IN').upper().strip()
    rows = (
        db.query(CalendarHoliday)
        .filter(
            CalendarHoliday.country_code == clean_country,
            CalendarHoliday.holiday_date >= start_date,
            CalendarHoliday.holiday_date <= end_date,
        )
        .order_by(CalendarHoliday.holiday_date.asc(), CalendarHoliday.name.asc())
        .all()
    )
    return [
        {
            'date': row.holiday_date.isoformat(),
            'name': row.name,
            'local_name': row.local_name or row.name,
            'is_national': bool(row.is_national),
        }
        for row in rows
    ]


def get_teacher_calendar(
    db: Session,
    teacher_id: int,
    start_date: date,
    end_date: date,
    view: str,
    *,
    actor_role: str = 'teacher',
    actor_user_id: int | None = None,
    bypass_cache: bool = False,
) -> dict[str, Any]:
    items = get_teacher_calendar_view(
        db,
        teacher_id,
        start_date,
        end_date,
        view,
        actor_role=actor_role,
        actor_user_id=actor_user_id,
        bypass_cache=bypass_cache,
    )
    prefs: dict[str, Any] | None = None
    if teacher_id:
        user = db.query(AuthUser).filter(AuthUser.id == teacher_id).first()
        if user:
            raw = user.calendar_preferences or '{}'
            try:
                prefs = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except Exception:
                prefs = {}
            prefs['snap_interval'] = int(user.calendar_snap_minutes or prefs.get('snap_interval') or 30)
            prefs['default_view'] = user.calendar_view_preference or prefs.get('default_view') or 'week'
            prefs.setdefault('work_day_start', '07:00')
            prefs.setdefault('work_day_end', '20:00')
            if user.default_event_color:
                prefs['default_event_color'] = user.default_event_color
            prefs['enable_live_mode_auto_open'] = bool(
                user.enable_live_mode_auto_open if user.enable_live_mode_auto_open is not None else True
            )
    holidays = get_calendar_holidays(
        db,
        start_date=start_date,
        end_date=end_date,
        country_code='IN',
    )

    return {
        'items': items,
        'holidays': holidays,
        'preferences': json.dumps(
            prefs
            or {
                'snap_interval': 30,
                'work_day_start': '07:00',
                'work_day_end': '20:00',
                'default_view': 'week',
                'enable_live_mode_auto_open': True,
            }
        ),
    }


def validate_calendar_conflicts(
    db: Session,
    teacher_id: int,
    target_date: date,
    start_time: str,
    duration_minutes: int,
    room_id: int | None = None,
) -> dict[str, Any]:
    if duration_minutes <= 0 or duration_minutes > 600:
        raise ValueError('duration_minutes must be between 1 and 600')

    start_dt = datetime.combine(target_date, _parse_time(start_time))
    end_dt = start_dt + timedelta(minutes=int(duration_minutes))

    conflicts: list[dict[str, Any]] = []

    teacher_sessions = (
        db.query(ClassSession)
        .filter(
            ClassSession.teacher_id == teacher_id,
            ClassSession.scheduled_start < end_dt,
            ClassSession.scheduled_start >= start_dt - timedelta(hours=6),
        )
        .all()
    )
    for session in teacher_sessions:
        session_end = session.scheduled_start + timedelta(minutes=int(session.duration_minutes or 60))
        if start_dt < session_end and session.scheduled_start < end_dt:
            conflicts.append(
                {
                    'type': 'teacher_conflict',
                    'session_id': session.id,
                    'batch_id': session.batch_id,
                    'start_datetime': session.scheduled_start.isoformat(),
                    'duration_minutes': session.duration_minutes,
                    'message': 'Teacher already has a class scheduled.',
                }
            )

    if room_id:
        room_batches = db.query(Batch.id).filter(Batch.room_id == room_id).all()
        room_batch_ids = [bid for (bid,) in room_batches]
        if room_batch_ids:
            room_sessions = (
                db.query(ClassSession)
                .filter(
                    ClassSession.batch_id.in_(room_batch_ids),
                    ClassSession.scheduled_start < end_dt,
                    ClassSession.scheduled_start >= start_dt - timedelta(hours=6),
                )
                .all()
            )
            for session in room_sessions:
                session_end = session.scheduled_start + timedelta(minutes=int(session.duration_minutes or 60))
                if start_dt < session_end and session.scheduled_start < end_dt:
                    conflicts.append(
                        {
                            'type': 'room_conflict',
                            'session_id': session.id,
                            'batch_id': session.batch_id,
                            'start_datetime': session.scheduled_start.isoformat(),
                            'duration_minutes': session.duration_minutes,
                            'message': 'Room already booked for another class.',
                        }
                    )

    return {
        'ok': len(conflicts) == 0,
        'conflicts': conflicts,
        'detail': None if len(conflicts) == 0 else 'Conflict detected.',
    }


def get_calendar_session_detail(db: Session, session_id: int) -> dict[str, Any] | None:
    row = (
        db.query(ClassSession)
        .options(selectinload(ClassSession.batch))
        .filter(ClassSession.id == session_id)
        .first()
    )
    if not row:
        return None
    end_dt = row.scheduled_start + timedelta(minutes=int(row.duration_minutes or 60))
    now = datetime.now()
    status, attendance_status = _session_status_label(
        now=now,
        start_dt=row.scheduled_start,
        end_dt=end_dt,
        session=row,
    )
    return {
        'session_id': row.id,
        'batch_id': row.batch_id,
        'batch_name': row.batch.name if row.batch else None,
        'subject': row.subject,
        'scheduled_start': row.scheduled_start.isoformat() if row.scheduled_start else None,
        'duration_minutes': row.duration_minutes,
        'status': status,
        'attendance_status': attendance_status,
        'topic_planned': row.topic_planned,
        'topic_completed': row.topic_completed,
        'teacher_id': row.teacher_id,
    }


def clear_teacher_calendar_cache() -> None:
    cache.invalidate_prefix('teacher_calendar')


def get_teacher_calendar_analytics(
    db: Session,
    teacher_id: int,
    start_date: date,
    end_date: date,
    *,
    actor_role: str = 'teacher',
    actor_user_id: int | None = None,
    bypass_cache: bool = False,
) -> dict[str, Any]:
    if end_date < start_date:
        raise ValueError('end_date must be greater than or equal to start_date')

    cache_token = _calendar_cache_key(
        role=(actor_role or 'teacher').lower(),
        actor_user_id=actor_user_id,
        teacher_id=int(teacher_id),
        start_date=start_date,
        end_date=end_date,
        view='analytics',
    )
    if not bypass_cache:
        cached = cache.get_cached(cache_token)
        if cached is not None:
            return cached

    if teacher_id:
        teacher_batch_ids = {
            int(batch_id)
            for (batch_id,) in db.query(ClassSession.batch_id)
            .filter(ClassSession.teacher_id == teacher_id)
            .distinct()
            .all()
            if batch_id is not None
        }
    else:
        teacher_batch_ids = set()

    # Fallback to active scheduled batches so analytics scope matches calendar scope,
    # especially for admin/global view (teacher_id=0) and for setups without class_sessions yet.
    if not teacher_batch_ids:
        teacher_batch_ids = {
            int(batch_id)
            for (batch_id,) in (
                db.query(BatchSchedule.batch_id)
                .join(Batch, Batch.id == BatchSchedule.batch_id)
                .filter(Batch.active.is_(True))
                .distinct()
                .all()
            )
            if batch_id is not None
        }

    if not teacher_batch_ids:
        payload = {'range': {'start': start_date.isoformat(), 'end': end_date.isoformat()}, 'days': []}
        cache.set_cached(cache_token, payload, ttl=CALENDAR_TTL_SECONDS)
        return payload

    total_students = int(
        db.query(func.count(func.distinct(StudentBatchMap.student_id)))
        .filter(
            StudentBatchMap.batch_id.in_(teacher_batch_ids),
            StudentBatchMap.active.is_(True),
        )
        .scalar()
        or 0
    )

    present_case = func.sum(
        case(
            (AttendanceRecord.status.in_(['Present', 'Late']), 1),
            else_=0,
        )
    )
    attendance_rows = (
        db.query(AttendanceRecord.attendance_date, present_case)
        .join(Student, Student.id == AttendanceRecord.student_id)
        .filter(
            AttendanceRecord.attendance_date >= start_date,
            AttendanceRecord.attendance_date <= end_date,
            Student.batch_id.in_(teacher_batch_ids),
        )
        .group_by(AttendanceRecord.attendance_date)
        .all()
    )
    present_by_day = {row[0]: int(row[1] or 0) for row in attendance_rows}

    days = []
    cursor = start_date
    while cursor <= end_date:
        present_count = present_by_day.get(cursor, 0)
        rate = (present_count / total_students) if total_students else None
        days.append(
            {
                'date': cursor.isoformat(),
                'present_count': present_count,
                'total_students': total_students,
                'attendance_rate': rate,
            }
        )
        cursor = cursor + timedelta(days=1)

    payload = {'range': {'start': start_date.isoformat(), 'end': end_date.isoformat()}, 'days': days}
    cache.set_cached(cache_token, payload, ttl=CALENDAR_TTL_SECONDS)
    return payload
