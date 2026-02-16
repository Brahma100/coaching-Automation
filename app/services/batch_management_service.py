from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AuthUser, Batch, BatchSchedule, CalendarOverride, ClassSession, Student, StudentBatchMap
from app.services.comms_service import queue_teacher_telegram
from app.services.daily_teacher_brief_service import resolve_teacher_chat_id
from app.services.student_notification_service import notify_student
from app.services.teacher_calendar_service import clear_teacher_calendar_cache
from app.services.time_capacity_service import clear_time_capacity_cache
from app.services.batch_membership_service import (
    deactivate_student_batch_mapping,
    ensure_active_student_batch_mapping,
    list_active_batches_for_student,
)

_WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def _parse_start_minutes(start_time: str) -> int:
    hh, mm = start_time.split(':', 1)
    hour = int(hh)
    minute = int(mm)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError('start_time must be HH:MM')
    return hour * 60 + minute


def _validate_duration(duration_minutes: int) -> None:
    if duration_minutes <= 0 or duration_minutes > 180:
        raise ValueError('duration_minutes must be between 1 and 180')


def _validate_weekday(weekday: int) -> None:
    if weekday < 0 or weekday > 6:
        raise ValueError('weekday must be between 0 and 6')


def _validate_no_overlap(
    db: Session,
    batch_id: int,
    weekday: int,
    start_time: str,
    duration_minutes: int,
    exclude_schedule_id: int | None = None,
) -> None:
    start_minutes = _parse_start_minutes(start_time)
    end_minutes = start_minutes + duration_minutes

    query = (
        db.query(BatchSchedule, Batch)
        .join(Batch, Batch.id == BatchSchedule.batch_id)
        .filter(
            Batch.active.is_(True),
            BatchSchedule.weekday == weekday,
        )
    )
    if exclude_schedule_id:
        query = query.filter(BatchSchedule.id != exclude_schedule_id)
    rows = query.all()

    for row, row_batch in rows:
        row_start = _parse_start_minutes(row.start_time)
        row_end = row_start + row.duration_minutes
        if not (end_minutes <= row_start or start_minutes >= row_end):
            if int(row.batch_id) == int(batch_id):
                raise ValueError('Schedule overlaps with existing slot for this batch and weekday')
            raise ValueError(
                f"Schedule overlaps with batch '{row_batch.name}' on this weekday"
            )


def _schedule_or_default_start_and_duration(
    db: Session,
    *,
    batch: Batch,
    weekday: int,
    new_start_time: str | None,
    new_duration_minutes: int | None,
) -> tuple[str, int]:
    schedule = (
        db.query(BatchSchedule)
        .filter(BatchSchedule.batch_id == batch.id, BatchSchedule.weekday == weekday)
        .order_by(BatchSchedule.start_time.asc(), BatchSchedule.id.asc())
        .first()
    )
    start_value = (new_start_time or '').strip() or (schedule.start_time if schedule else '')
    if not start_value:
        raise ValueError('new_start_time is required because no base schedule exists for this day')
    _parse_start_minutes(start_value)
    duration_value = int(new_duration_minutes or (schedule.duration_minutes if schedule else batch.default_duration_minutes or 60))
    _validate_duration(duration_value)
    return start_value, duration_value


def validate_strict_slot_conflict(
    db: Session,
    *,
    batch_id: int,
    target_date: date,
    new_start_time: str | None,
    new_duration_minutes: int | None,
) -> None:
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise ValueError('Batch not found')

    weekday = int(target_date.weekday())
    start_time_value, duration_value = _schedule_or_default_start_and_duration(
        db,
        batch=batch,
        weekday=weekday,
        new_start_time=new_start_time,
        new_duration_minutes=new_duration_minutes,
    )
    start_minutes = _parse_start_minutes(start_time_value)
    end_minutes = start_minutes + duration_value

    schedule_rows = (
        db.query(BatchSchedule, Batch)
        .join(Batch, Batch.id == BatchSchedule.batch_id)
        .filter(
            Batch.active.is_(True),
            BatchSchedule.weekday == weekday,
            BatchSchedule.batch_id != batch_id,
        )
        .all()
    )
    other_batch_ids = {int(row.batch_id) for row, _ in schedule_rows}
    override_rows = (
        db.query(CalendarOverride)
        .filter(
            CalendarOverride.override_date == target_date,
            CalendarOverride.batch_id != batch_id,
        )
        .order_by(CalendarOverride.id.asc())
        .all()
    )
    latest_override_by_batch: dict[int, CalendarOverride] = {}
    for row in override_rows:
        latest_override_by_batch[int(row.batch_id)] = row

    for row, row_batch in schedule_rows:
        override = latest_override_by_batch.get(int(row.batch_id))
        if override and override.cancelled:
            continue
        start_text = override.new_start_time if override and override.new_start_time else row.start_time
        duration = int(override.new_duration_minutes if override and override.new_duration_minutes else row.duration_minutes)
        row_start = _parse_start_minutes(start_text)
        row_end = row_start + duration
        if not (end_minutes <= row_start or start_minutes >= row_end):
            raise ValueError(f"Slot overlaps with batch '{row_batch.name}'")

    override_only_batch_ids = set(latest_override_by_batch.keys()) - other_batch_ids
    if override_only_batch_ids:
        override_batch_rows = db.query(Batch).filter(Batch.id.in_(override_only_batch_ids)).all()
        override_batch_map = {int(row.id): row for row in override_batch_rows}
        for obid in sorted(override_only_batch_ids):
            override = latest_override_by_batch.get(obid)
            if not override or override.cancelled or not override.new_start_time:
                continue
            duration = int(override.new_duration_minutes or 60)
            row_start = _parse_start_minutes(override.new_start_time)
            row_end = row_start + duration
            if not (end_minutes <= row_start or start_minutes >= row_end):
                row_batch = override_batch_map.get(obid)
                name = row_batch.name if row_batch else f'Batch {obid}'
                raise ValueError(f"Slot overlaps with batch '{name}'")

    class_rows = (
        db.query(ClassSession, Batch)
        .join(Batch, Batch.id == ClassSession.batch_id, isouter=True)
        .filter(
            func.date(ClassSession.scheduled_start) == target_date,
            ClassSession.batch_id != batch_id,
            ClassSession.status != 'cancelled',
        )
        .all()
    )
    for session, row_batch in class_rows:
        row_start_dt = session.scheduled_start
        row_start = (int(row_start_dt.hour) * 60) + int(row_start_dt.minute)
        row_end = row_start + int(session.duration_minutes or 60)
        if not (end_minutes <= row_start or start_minutes >= row_end):
            name = row_batch.name if row_batch else f'Batch {session.batch_id}'
            raise ValueError(f"Slot overlaps with batch '{name}'")


def create_batch(
    db: Session,
    *,
    name: str,
    subject: str,
    academic_level: str,
    max_students: int | None = None,
    active: bool = True,
    actor: dict | None = None,
) -> Batch:
    clean_name = (name or '').strip()
    if not clean_name:
        raise ValueError('Batch name is required')
    exists = db.query(Batch).filter(func.lower(Batch.name) == clean_name.lower()).first()
    if exists:
        raise ValueError('Batch name already exists')

    actor_center_id = int((actor or {}).get('center_id') or 0)
    if actor_center_id <= 0:
        actor_center_id = 1
    row = Batch(
        name=clean_name,
        subject=(subject or 'General').strip() or 'General',
        academic_level=(academic_level or '').strip(),
        max_students=max_students,
        center_id=actor_center_id,
        active=active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    clear_teacher_calendar_cache()
    clear_time_capacity_cache()
    _notify_batch_change(db, action='created', batch=row, actor=actor)
    return row


def update_batch(
    db: Session,
    batch_id: int,
    *,
    name: str,
    subject: str,
    academic_level: str,
    max_students: int | None = None,
    active: bool,
    actor: dict | None = None,
) -> Batch:
    row = db.query(Batch).filter(Batch.id == batch_id).first()
    if not row:
        raise ValueError('Batch not found')

    clean_name = (name or '').strip()
    if not clean_name:
        raise ValueError('Batch name is required')
    conflict = (
        db.query(Batch)
        .filter(func.lower(Batch.name) == clean_name.lower(), Batch.id != batch_id)
        .first()
    )
    if conflict:
        raise ValueError('Batch name already exists')

    row.name = clean_name
    row.subject = (subject or 'General').strip() or 'General'
    row.academic_level = (academic_level or '').strip()
    row.max_students = max_students
    row.active = bool(active)
    db.commit()
    db.refresh(row)
    clear_teacher_calendar_cache()
    clear_time_capacity_cache()
    _notify_batch_change(db, action='updated', batch=row, actor=actor)
    return row


def soft_delete_batch(db: Session, batch_id: int, actor: dict | None = None) -> Batch:
    row = db.query(Batch).filter(Batch.id == batch_id).first()
    if not row:
        raise ValueError('Batch not found')
    students = (
        db.query(StudentBatchMap, Student)
        .join(Student, Student.id == StudentBatchMap.student_id)
        .filter(
            StudentBatchMap.batch_id == int(batch_id),
            StudentBatchMap.active.is_(True),
        )
        .all()
    )
    row.active = False
    db.commit()
    db.refresh(row)
    for _, student in students:
        notify_student(
            db,
            student=student,
            message=(
                "Batch update\n"
                f"Batch '{row.name}' is no longer active.\n"
                "Please contact your coaching admin for reassignment."
            ),
            notification_type="student_batch_deleted",
            critical=True,
        )
    clear_teacher_calendar_cache()
    clear_time_capacity_cache()
    _notify_batch_change(db, action='deleted', batch=row, actor=actor)
    return row


def add_schedule(
    db: Session,
    batch_id: int,
    *,
    weekday: int,
    start_time: str,
    duration_minutes: int,
    actor: dict | None = None,
) -> BatchSchedule:
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise ValueError('Batch not found')
    _validate_weekday(weekday)
    _validate_duration(duration_minutes)
    _parse_start_minutes(start_time)
    _validate_no_overlap(db, batch_id, weekday, start_time, duration_minutes)

    row = BatchSchedule(
        batch_id=batch_id,
        weekday=weekday,
        start_time=start_time,
        duration_minutes=duration_minutes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    clear_teacher_calendar_cache()
    clear_time_capacity_cache()
    _notify_schedule_change(db, action='created', batch=batch, schedule=row, actor=actor)
    return row


def update_schedule(
    db: Session,
    schedule_id: int,
    *,
    weekday: int,
    start_time: str,
    duration_minutes: int,
    actor: dict | None = None,
) -> BatchSchedule:
    row = db.query(BatchSchedule).filter(BatchSchedule.id == schedule_id).first()
    if not row:
        raise ValueError('Schedule not found')
    old_schedule = {
        'weekday': int(row.weekday),
        'start_time': str(row.start_time),
        'duration_minutes': int(row.duration_minutes),
    }
    _validate_weekday(weekday)
    _validate_duration(duration_minutes)
    _parse_start_minutes(start_time)
    _validate_no_overlap(
        db,
        row.batch_id,
        weekday,
        start_time,
        duration_minutes,
        exclude_schedule_id=row.id,
    )

    row.weekday = weekday
    row.start_time = start_time
    row.duration_minutes = duration_minutes
    db.commit()
    db.refresh(row)
    clear_teacher_calendar_cache()
    clear_time_capacity_cache()
    batch = db.query(Batch).filter(Batch.id == row.batch_id).first()
    if batch:
        _notify_schedule_change(db, action='updated', batch=batch, schedule=row, actor=actor, old_schedule=old_schedule)
    return row


def delete_schedule(db: Session, schedule_id: int, actor: dict | None = None) -> None:
    row = db.query(BatchSchedule).filter(BatchSchedule.id == schedule_id).first()
    if not row:
        raise ValueError('Schedule not found')
    batch = db.query(Batch).filter(Batch.id == row.batch_id).first()
    if batch:
        _notify_schedule_change(db, action='deleted', batch=batch, schedule=row, actor=actor)
    db.delete(row)
    db.commit()
    clear_teacher_calendar_cache()
    clear_time_capacity_cache()


def _notify_membership_change(
    db: Session,
    *,
    action: str,
    batch: Batch,
    student: Student,
    actor: dict | None,
) -> None:
    if not actor:
        return
    teacher_id = int(actor.get('user_id') or 0)
    teacher_phone = str(actor.get('phone') or '').strip()
    if teacher_id <= 0 or not teacher_phone:
        return
    chat_id = resolve_teacher_chat_id(db, teacher_phone)
    if not chat_id:
        return

    teacher = db.query(AuthUser).filter(AuthUser.id == teacher_id).first()
    teacher_label = teacher.phone if teacher else teacher_phone
    message = (
        f"Batch membership updated\n"
        f"Action: {action}\n"
        f"Teacher: {teacher_label} (id={teacher_id})\n"
        f"Student: {student.name} (id={student.id}, phone={student.guardian_phone})\n"
        f"Batch: {batch.name} (id={batch.id}, subject={batch.subject}, level={batch.academic_level})"
    )
    queue_teacher_telegram(
        db,
        teacher_id=teacher_id,
        chat_id=chat_id,
        message=message,
        batch_id=batch.id,
        notification_type='batch_membership_change',
        session_id=None,
    )


def _notify_student_membership_change(
    db: Session,
    *,
    action: str,
    batch: Batch,
    student: Student,
) -> None:
    if action == "linked":
        message = (
            "Enrollment updated\n"
            f"You are enrolled in batch: {batch.name}\n"
            f"Subject: {batch.subject}\n"
            f"Level: {batch.academic_level or 'N/A'}"
        )
    else:
        message = (
            "Enrollment updated\n"
            f"You are removed from batch: {batch.name}\n"
            f"Subject: {batch.subject}"
        )
    notify_student(
        db,
        student=student,
        message=message,
        notification_type="student_batch_membership_change",
        critical=True,
    )


def _notify_batch_change(
    db: Session,
    *,
    action: str,
    batch: Batch,
    actor: dict | None,
) -> None:
    if not actor:
        return
    teacher_id = int(actor.get('user_id') or 0)
    teacher_phone = str(actor.get('phone') or '').strip()
    if teacher_id <= 0 or not teacher_phone:
        return
    chat_id = resolve_teacher_chat_id(db, teacher_phone)
    if not chat_id:
        return
    teacher = db.query(AuthUser).filter(AuthUser.id == teacher_id).first()
    teacher_label = teacher.phone if teacher else teacher_phone
    message = (
        f"Batch updated\n"
        f"Action: {action}\n"
        f"Teacher: {teacher_label} (id={teacher_id})\n"
        f"Batch: {batch.name} (id={batch.id}, subject={batch.subject}, level={batch.academic_level}, active={batch.active})"
    )
    queue_teacher_telegram(
        db,
        teacher_id=teacher_id,
        chat_id=chat_id,
        message=message,
        batch_id=batch.id,
        notification_type='batch_change',
        session_id=None,
    )


def _notify_schedule_change(
    db: Session,
    *,
    action: str,
    batch: Batch,
    schedule: BatchSchedule,
    actor: dict | None,
    old_schedule: dict | None = None,
) -> None:
    mappings = (
        db.query(StudentBatchMap, Student)
        .join(Student, Student.id == StudentBatchMap.student_id)
        .filter(
            StudentBatchMap.batch_id == int(batch.id),
            StudentBatchMap.active.is_(True),
        )
        .all()
    )
    for _, student in mappings:
        if action == 'created':
            student_message = (
                "Batch schedule updated\n"
                f"Batch: {batch.name}\n"
                f"New slot: {_WEEKDAY_LABELS[int(schedule.weekday)]} {schedule.start_time} ({int(schedule.duration_minutes)}m)"
            )
        elif action == 'deleted':
            student_message = (
                "Batch schedule updated\n"
                f"Batch: {batch.name}\n"
                f"Removed slot: {_WEEKDAY_LABELS[int(schedule.weekday)]} {schedule.start_time} ({int(schedule.duration_minutes)}m)"
            )
        else:
            old_weekday = int(old_schedule.get('weekday')) if old_schedule else int(schedule.weekday)
            old_start = str(old_schedule.get('start_time')) if old_schedule else str(schedule.start_time)
            old_duration = int(old_schedule.get('duration_minutes')) if old_schedule else int(schedule.duration_minutes)
            student_message = (
                "Batch schedule updated\n"
                f"Batch: {batch.name}\n"
                f"Old: {_WEEKDAY_LABELS[old_weekday]} {old_start} ({old_duration}m)\n"
                f"New: {_WEEKDAY_LABELS[int(schedule.weekday)]} {schedule.start_time} ({int(schedule.duration_minutes)}m)"
            )
        notify_student(
            db,
            student=student,
            message=student_message,
            notification_type='student_batch_schedule_change',
            critical=True,
        )

    if not actor:
        return
    teacher_id = int(actor.get('user_id') or 0)
    teacher_phone = str(actor.get('phone') or '').strip()
    if teacher_id <= 0 or not teacher_phone:
        return
    chat_id = resolve_teacher_chat_id(db, teacher_phone)
    if not chat_id:
        return
    teacher = db.query(AuthUser).filter(AuthUser.id == teacher_id).first()
    teacher_label = teacher.phone if teacher else teacher_phone
    message = (
        f"Batch schedule updated\n"
        f"Action: {action}\n"
        f"Teacher: {teacher_label} (id={teacher_id})\n"
        f"Batch: {batch.name} (id={batch.id}, subject={batch.subject}, level={batch.academic_level})\n"
        f"Schedule: id={schedule.id}, weekday={schedule.weekday}, start={schedule.start_time}, duration={schedule.duration_minutes}m"
    )
    queue_teacher_telegram(
        db,
        teacher_id=teacher_id,
        chat_id=chat_id,
        message=message,
        batch_id=batch.id,
        notification_type='batch_schedule_change',
        session_id=None,
    )


def link_student_to_batch(db: Session, batch_id: int, student_id: int, actor: dict | None = None) -> StudentBatchMap:
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise ValueError('Batch not found')
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise ValueError('Student not found')
    mapping = ensure_active_student_batch_mapping(db, student_id=student_id, batch_id=batch_id)
    clear_teacher_calendar_cache()
    clear_time_capacity_cache()
    _notify_membership_change(db, action='linked', batch=batch, student=student, actor=actor)
    _notify_student_membership_change(db, action='linked', batch=batch, student=student)
    return mapping


def unlink_student_from_batch(db: Session, batch_id: int, student_id: int, actor: dict | None = None) -> StudentBatchMap:
    mapping = deactivate_student_batch_mapping(db, student_id=student_id, batch_id=batch_id)
    if not mapping:
        raise ValueError('Active student-batch mapping not found')
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    student = db.query(Student).filter(Student.id == student_id).first()
    if batch and student:
        _notify_membership_change(db, action='unlinked', batch=batch, student=student, actor=actor)
        _notify_student_membership_change(db, action='unlinked', batch=batch, student=student)
    clear_teacher_calendar_cache()
    clear_time_capacity_cache()
    return mapping


def serialize_schedule(row: BatchSchedule) -> dict:
    return {
        'id': row.id,
        'batch_id': row.batch_id,
        'weekday': row.weekday,
        'start_time': row.start_time,
        'duration_minutes': row.duration_minutes,
        'created_at': row.created_at.isoformat() if row.created_at else None,
    }


def list_batches_with_details(
    db: Session,
    include_inactive: bool = True,
    *,
    for_date: date | None = None,
) -> list[dict]:
    query = db.query(Batch)
    if not include_inactive:
        query = query.filter(Batch.active.is_(True))
    rows = query.order_by(Batch.name.asc()).all()

    batch_ids = [row.id for row in rows]
    schedules_by_batch: dict[int, list[BatchSchedule]] = {}
    active_students_by_batch: dict[int, int] = {}
    effective_schedule_by_batch: dict[int, dict] = {}
    if batch_ids:
        schedules = (
            db.query(BatchSchedule)
            .filter(BatchSchedule.batch_id.in_(batch_ids))
            .order_by(BatchSchedule.weekday.asc(), BatchSchedule.start_time.asc(), BatchSchedule.id.asc())
            .all()
        )
        for schedule in schedules:
            schedules_by_batch.setdefault(schedule.batch_id, []).append(schedule)

        counts = (
            db.query(StudentBatchMap.batch_id, func.count(func.distinct(StudentBatchMap.student_id)))
            .filter(
                StudentBatchMap.batch_id.in_(batch_ids),
                StudentBatchMap.active.is_(True),
            )
            .group_by(StudentBatchMap.batch_id)
            .all()
        )
        active_students_by_batch = {batch_id: count for (batch_id, count) in counts}

        if for_date is not None:
            override_rows = (
                db.query(CalendarOverride)
                .filter(
                    CalendarOverride.batch_id.in_(batch_ids),
                    CalendarOverride.override_date == for_date,
                )
                .order_by(CalendarOverride.id.asc())
                .all()
            )
            latest_override_by_batch: dict[int, CalendarOverride] = {}
            for row in override_rows:
                latest_override_by_batch[int(row.batch_id)] = row

            target_weekday = int(for_date.weekday())
            for row in rows:
                batch_id = int(row.id)
                schedules_for_day = [
                    schedule
                    for schedule in schedules_by_batch.get(batch_id, [])
                    if int(schedule.weekday) == target_weekday
                ]
                base_schedule = schedules_for_day[0] if schedules_for_day else None
                override = latest_override_by_batch.get(batch_id)
                if override and override.cancelled:
                    effective_schedule_by_batch[batch_id] = {
                        'date': for_date.isoformat(),
                        'weekday': target_weekday,
                        'start_time': None,
                        'duration_minutes': None,
                        'source': 'override_cancelled',
                        'override_id': int(override.id),
                        'cancelled': True,
                        'reason': (override.reason or '').strip(),
                    }
                    continue

                if override and override.new_start_time:
                    duration = int(
                        override.new_duration_minutes
                        or (base_schedule.duration_minutes if base_schedule else row.default_duration_minutes or 60)
                    )
                    effective_schedule_by_batch[batch_id] = {
                        'date': for_date.isoformat(),
                        'weekday': target_weekday,
                        'start_time': override.new_start_time,
                        'duration_minutes': duration,
                        'source': 'override',
                        'override_id': int(override.id),
                        'cancelled': False,
                        'reason': (override.reason or '').strip(),
                    }
                    continue

                if base_schedule:
                    effective_schedule_by_batch[batch_id] = {
                        'date': for_date.isoformat(),
                        'weekday': target_weekday,
                        'start_time': base_schedule.start_time,
                        'duration_minutes': int(base_schedule.duration_minutes or row.default_duration_minutes or 60),
                        'source': 'schedule',
                        'override_id': int(override.id) if override else None,
                        'cancelled': False,
                        'reason': (override.reason or '').strip() if override else '',
                    }
                else:
                    effective_schedule_by_batch[batch_id] = {
                        'date': for_date.isoformat(),
                        'weekday': target_weekday,
                        'start_time': None,
                        'duration_minutes': None,
                        'source': 'none',
                        'override_id': int(override.id) if override else None,
                        'cancelled': False,
                        'reason': (override.reason or '').strip() if override else '',
                    }

    payload = []
    for row in rows:
        payload.append(
            {
                'id': row.id,
                'name': row.name,
                'subject': row.subject,
                'academic_level': row.academic_level,
                'active': row.active,
                'created_at': row.created_at.isoformat() if row.created_at else None,
                'start_time': row.start_time,
                'max_students': row.max_students,
                'student_count': int(active_students_by_batch.get(row.id, 0)),
                'schedules': [serialize_schedule(s) for s in schedules_by_batch.get(row.id, [])],
                'effective_schedule_for_date': effective_schedule_by_batch.get(int(row.id)) if for_date is not None else None,
            }
        )
    return payload


def get_batch_detail(db: Session, batch_id: int) -> dict:
    row = db.query(Batch).filter(Batch.id == batch_id).first()
    if not row:
        raise ValueError('Batch not found')
    records = list_batches_with_details(db, include_inactive=True)
    for record in records:
        if record['id'] == batch_id:
            return record
    raise ValueError('Batch not found')


def list_students_for_batch(db: Session, batch_id: int) -> list[dict]:
    rows = (
        db.query(StudentBatchMap, Student)
        .join(Student, Student.id == StudentBatchMap.student_id)
        .filter(
            StudentBatchMap.batch_id == batch_id,
            StudentBatchMap.active.is_(True),
        )
        .order_by(Student.name.asc(), Student.id.asc())
        .all()
    )
    return [
        {
            'student_id': student.id,
            'name': student.name,
            'phone': student.guardian_phone,
            'joined_at': mapping.joined_at.isoformat() if mapping.joined_at else None,
        }
        for mapping, student in rows
    ]


def list_all_students(db: Session) -> list[Student]:
    return db.query(Student).order_by(Student.name.asc()).all()


def list_batches_for_student(db: Session, student_id: int) -> list[dict]:
    rows = list_active_batches_for_student(db, student_id)
    return [
        {
            'id': row.id,
            'name': row.name,
            'subject': row.subject,
            'academic_level': row.academic_level,
            'active': row.active,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
