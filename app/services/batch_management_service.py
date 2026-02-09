from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Batch, BatchSchedule, Student, StudentBatchMap
from app.services.batch_membership_service import (
    deactivate_student_batch_mapping,
    ensure_active_student_batch_mapping,
    list_active_batches_for_student,
)


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

    query = db.query(BatchSchedule).filter(
        BatchSchedule.batch_id == batch_id,
        BatchSchedule.weekday == weekday,
    )
    if exclude_schedule_id:
        query = query.filter(BatchSchedule.id != exclude_schedule_id)
    rows = query.all()

    for row in rows:
        row_start = _parse_start_minutes(row.start_time)
        row_end = row_start + row.duration_minutes
        if not (end_minutes <= row_start or start_minutes >= row_end):
            raise ValueError('Schedule overlaps with existing slot for this batch and weekday')


def create_batch(db: Session, *, name: str, subject: str, academic_level: str, active: bool = True) -> Batch:
    clean_name = (name or '').strip()
    if not clean_name:
        raise ValueError('Batch name is required')
    exists = db.query(Batch).filter(func.lower(Batch.name) == clean_name.lower()).first()
    if exists:
        raise ValueError('Batch name already exists')

    row = Batch(
        name=clean_name,
        subject=(subject or 'General').strip() or 'General',
        academic_level=(academic_level or '').strip(),
        active=active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_batch(
    db: Session,
    batch_id: int,
    *,
    name: str,
    subject: str,
    academic_level: str,
    active: bool,
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
    row.active = bool(active)
    db.commit()
    db.refresh(row)
    return row


def soft_delete_batch(db: Session, batch_id: int) -> Batch:
    row = db.query(Batch).filter(Batch.id == batch_id).first()
    if not row:
        raise ValueError('Batch not found')
    row.active = False
    db.commit()
    db.refresh(row)
    return row


def add_schedule(db: Session, batch_id: int, *, weekday: int, start_time: str, duration_minutes: int) -> BatchSchedule:
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
    return row


def update_schedule(db: Session, schedule_id: int, *, weekday: int, start_time: str, duration_minutes: int) -> BatchSchedule:
    row = db.query(BatchSchedule).filter(BatchSchedule.id == schedule_id).first()
    if not row:
        raise ValueError('Schedule not found')
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
    return row


def delete_schedule(db: Session, schedule_id: int) -> None:
    row = db.query(BatchSchedule).filter(BatchSchedule.id == schedule_id).first()
    if not row:
        raise ValueError('Schedule not found')
    db.delete(row)
    db.commit()


def link_student_to_batch(db: Session, batch_id: int, student_id: int) -> StudentBatchMap:
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise ValueError('Batch not found')
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise ValueError('Student not found')
    mapping = ensure_active_student_batch_mapping(db, student_id=student_id, batch_id=batch_id)
    return mapping


def unlink_student_from_batch(db: Session, batch_id: int, student_id: int) -> StudentBatchMap:
    mapping = deactivate_student_batch_mapping(db, student_id=student_id, batch_id=batch_id)
    if not mapping:
        raise ValueError('Active student-batch mapping not found')
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


def list_batches_with_details(db: Session, include_inactive: bool = True) -> list[dict]:
    query = db.query(Batch)
    if not include_inactive:
        query = query.filter(Batch.active.is_(True))
    rows = query.order_by(Batch.name.asc()).all()

    batch_ids = [row.id for row in rows]
    schedules_by_batch: dict[int, list[BatchSchedule]] = {}
    active_students_by_batch: dict[int, int] = {}
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
                'student_count': int(active_students_by_batch.get(row.id, 0)),
                'schedules': [serialize_schedule(s) for s in schedules_by_batch.get(row.id, [])],
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
