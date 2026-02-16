from __future__ import annotations

import json
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.models import AdminOpsSnapshot, AuthUser, Role, Student, StudentDashboardSnapshot, TeacherTodaySnapshot
from app.services.admin_ops_dashboard_service import get_admin_ops_dashboard
from app.services.dashboard_today_service import get_today_view
from app.services.observability_counters import record_observability_event
from app.services.student_portal_service import get_student_dashboard


logger = logging.getLogger(__name__)


def _canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, default=str)


def _canonical_row_payload(raw: str) -> str:
    try:
        return _canonical(json.loads(raw))
    except Exception:
        return ''


def _today(time_provider: TimeProvider = default_time_provider) -> date:
    return time_provider.today()


def rebuild_teacher_today_snapshot(
    db: Session,
    center_id: int,
    *,
    day: date | None = None,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    target_day = day or _today(time_provider)
    now = time_provider.now().replace(tzinfo=None)
    teachers = (
        db.query(AuthUser.id)
        .filter(
            AuthUser.role == Role.TEACHER.value,
            AuthUser.center_id == int(center_id or 0),
        )
        .all()
    )
    rebuilt = 0
    healed = 0
    for (teacher_id,) in teachers:
        payload = get_today_view(
            db,
            actor={'role': Role.TEACHER.value, 'user_id': int(teacher_id), 'center_id': int(center_id)},
            time_provider=time_provider,
        )
        row = (
            db.query(TeacherTodaySnapshot)
            .filter(
                TeacherTodaySnapshot.teacher_id == int(teacher_id),
                TeacherTodaySnapshot.date == target_day,
            )
            .first()
        )
        rebuilt += 1
        payload_json = _canonical(payload)
        if row is None:
            db.add(
                TeacherTodaySnapshot(
                    teacher_id=int(teacher_id),
                    date=target_day,
                    data_json=payload_json,
                    updated_at=now,
                )
            )
            healed += 1
            record_observability_event('snapshot_drift')
            logger.warning(
                'snapshot_drift_detected',
                extra={
                    'center_id': int(center_id),
                    'snapshot_type': 'teacher_today',
                    'entity_id': int(teacher_id),
                    'day': target_day.isoformat(),
                },
            )
            continue
        if _canonical_row_payload(str(row.data_json or '')) != payload_json:
            row.data_json = payload_json
            row.updated_at = now
            healed += 1
            record_observability_event('snapshot_drift')
            logger.warning(
                'snapshot_drift_detected',
                extra={
                    'center_id': int(center_id),
                    'snapshot_type': 'teacher_today',
                    'entity_id': int(teacher_id),
                    'day': target_day.isoformat(),
                },
            )
    db.commit()
    return {'rebuilt': rebuilt, 'healed': healed}


def rebuild_admin_ops_snapshot(
    db: Session,
    center_id: int,
    *,
    day: date | None = None,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    target_day = day or _today(time_provider)
    now = time_provider.now().replace(tzinfo=None)
    payload = get_admin_ops_dashboard(db, center_id=int(center_id or 0), time_provider=time_provider)
    payload_json = _canonical(payload)
    row = (
        db.query(AdminOpsSnapshot)
        .filter(
            AdminOpsSnapshot.center_id == int(center_id or 0),
            AdminOpsSnapshot.date == target_day,
        )
        .first()
    )
    rebuilt = 1
    healed = 0
    if row is None:
        db.add(
            AdminOpsSnapshot(
                center_id=int(center_id or 0),
                date=target_day,
                data_json=payload_json,
                updated_at=now,
            )
        )
        healed = 1
        record_observability_event('snapshot_drift')
        logger.warning(
            'snapshot_drift_detected',
            extra={
                'center_id': int(center_id),
                'snapshot_type': 'admin_ops',
                'entity_id': 0,
                'day': target_day.isoformat(),
            },
        )
    else:
        if _canonical_row_payload(str(row.data_json or '')) != payload_json:
            row.data_json = payload_json
            row.updated_at = now
            healed = 1
            record_observability_event('snapshot_drift')
            logger.warning(
                'snapshot_drift_detected',
                extra={
                    'center_id': int(center_id),
                    'snapshot_type': 'admin_ops',
                    'entity_id': 0,
                    'day': target_day.isoformat(),
                },
            )
    db.commit()
    return {'rebuilt': rebuilt, 'healed': healed}


def rebuild_student_dashboard_snapshot(
    db: Session,
    center_id: int,
    *,
    day: date | None = None,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    target_day = day or _today(time_provider)
    now = time_provider.now().replace(tzinfo=None)
    students = db.query(Student).filter(Student.center_id == int(center_id or 0)).all()
    rebuilt = 0
    healed = 0
    for student in students:
        payload = get_student_dashboard(db, student, time_provider=time_provider)
        payload_json = _canonical(payload)
        row = (
            db.query(StudentDashboardSnapshot)
            .filter(
                StudentDashboardSnapshot.student_id == int(student.id),
                StudentDashboardSnapshot.date == target_day,
            )
            .first()
        )
        rebuilt += 1
        if row is None:
            db.add(
                StudentDashboardSnapshot(
                    student_id=int(student.id),
                    date=target_day,
                    data_json=payload_json,
                    updated_at=now,
                )
            )
            healed += 1
            record_observability_event('snapshot_drift')
            logger.warning(
                'snapshot_drift_detected',
                extra={
                    'center_id': int(center_id),
                    'snapshot_type': 'student_dashboard',
                    'entity_id': int(student.id),
                    'day': target_day.isoformat(),
                },
            )
            continue
        if _canonical_row_payload(str(row.data_json or '')) != payload_json:
            row.data_json = payload_json
            row.updated_at = now
            healed += 1
            record_observability_event('snapshot_drift')
            logger.warning(
                'snapshot_drift_detected',
                extra={
                    'center_id': int(center_id),
                    'snapshot_type': 'student_dashboard',
                    'entity_id': int(student.id),
                    'day': target_day.isoformat(),
                },
            )
    db.commit()
    return {'rebuilt': rebuilt, 'healed': healed}


def rebuild_snapshots_for_center(
    db: Session,
    *,
    center_id: int,
    day: date | None = None,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    target_day = day or _today(time_provider)
    teacher = rebuild_teacher_today_snapshot(db, center_id, day=target_day, time_provider=time_provider)
    admin = rebuild_admin_ops_snapshot(db, center_id, day=target_day, time_provider=time_provider)
    student = rebuild_student_dashboard_snapshot(db, center_id, day=target_day, time_provider=time_provider)
    healed_count = int(teacher['healed']) + int(admin['healed']) + int(student['healed'])
    rebuilt_count = int(teacher['rebuilt']) + int(admin['rebuilt']) + int(student['rebuilt'])
    record_observability_event('snapshot_rebuild_run')
    logger.info(
        'snapshot_rebuild_run',
        extra={'center_id': int(center_id), 'rebuilt_count': rebuilt_count, 'day': target_day.isoformat()},
    )
    logger.info(
        'snapshot_rebuild_healed_count',
        extra={'center_id': int(center_id), 'healed_count': healed_count, 'day': target_day.isoformat()},
    )
    return {
        'center_id': int(center_id),
        'day': target_day.isoformat(),
        'rebuilt_count': rebuilt_count,
        'healed_count': healed_count,
        'teacher': teacher,
        'admin': admin,
        'student': student,
    }
