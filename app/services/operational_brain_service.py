from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.cache import cache, cache_key
from app.core.time_provider import TimeProvider, default_time_provider
from app.models import AttendanceRecord, Batch, Center, ClassSession, FeeRecord, PendingAction, Student, StudentRiskProfile
from app.services.access_scope_service import get_teacher_batch_ids
from app.services.dashboard_today_service import get_today_view
from app.services.time_capacity_service import get_batch_capacity


OPERATIONAL_BRAIN_TTL_SECONDS = 45


def clear_operational_brain_cache() -> None:
    cache.invalidate_prefix('operational_brain')


def _brain_cache_key(*, center_id: int, user_id: int, role: str) -> str:
    return cache_key('operational_brain', f'{center_id}:{user_id}:{role}')


def _next_upcoming_class(today_classes: list[dict], *, now: datetime) -> dict | None:
    window_end = now + timedelta(hours=2)
    candidates: list[dict] = []
    for row in today_classes:
        try:
            start_dt = datetime.fromisoformat(str(row.get('scheduled_start') or ''))
        except Exception:
            continue
        if start_dt < now or start_dt > window_end:
            continue
        item = dict(row)
        item['minutes_to_start'] = max(0, int((start_dt - now).total_seconds() // 60))
        candidates.append(item)
    if not candidates:
        return None
    candidates.sort(key=lambda row: row.get('scheduled_start') or '')
    return candidates[0]


def _pending_inbox_actions(
    db: Session,
    *,
    role: str,
    user_id: int,
    center_id: int,
    teacher_batch_ids: set[int] | None,
    limit: int = 20,
) -> list[dict]:
    query = db.query(PendingAction).filter(PendingAction.status == 'open')
    if center_id > 0:
        query = query.filter(PendingAction.center_id == center_id)
    if role == 'teacher':
        query = query.filter(PendingAction.teacher_id == user_id)

    rows = (
        query.order_by(
            PendingAction.due_at.is_(None),
            PendingAction.due_at.asc(),
            PendingAction.created_at.asc(),
            PendingAction.id.asc(),
        )
        .limit(max(1, int(limit)))
        .all()
    )
    if not rows:
        return []

    session_ids = {
        int(row.session_id or row.related_session_id)
        for row in rows
        if int(row.session_id or row.related_session_id or 0) > 0
    }
    student_ids = {int(row.student_id) for row in rows if int(row.student_id or 0) > 0}

    session_batch_map: dict[int, int] = {}
    if session_ids:
        session_rows = (
            db.query(ClassSession.id, ClassSession.batch_id)
            .filter(
                ClassSession.id.in_(session_ids),
                ClassSession.center_id == center_id if center_id > 0 else True,
            )
            .all()
        )
        session_batch_map = {int(session_id): int(batch_id) for session_id, batch_id in session_rows}

    student_rows = (
        db.query(Student.id, Student.name, Student.batch_id)
        .filter(Student.id.in_(student_ids), Student.center_id == center_id if center_id > 0 else True)
        .all()
        if student_ids
        else []
    )
    student_map = {
        int(student_id): {'student_name': str(name or ''), 'batch_id': int(batch_id or 0)}
        for student_id, name, batch_id in student_rows
    }

    payload: list[dict] = []
    now = default_time_provider.now().replace(tzinfo=None)
    for row in rows:
        batch_id = 0
        if int(row.session_id or row.related_session_id or 0) > 0:
            batch_id = int(session_batch_map.get(int(row.session_id or row.related_session_id or 0)) or 0)
        elif int(row.student_id or 0) > 0:
            batch_id = int((student_map.get(int(row.student_id or 0)) or {}).get('batch_id') or 0)

        if teacher_batch_ids is not None and batch_id not in teacher_batch_ids:
            continue

        due_at = row.due_at
        overdue_minutes = None
        if due_at is not None and due_at < now:
            overdue_minutes = max(1, int((now - due_at).total_seconds() // 60))
        payload.append(
            {
                'id': int(row.id),
                'action_type': str(row.action_type or row.type or ''),
                'student_id': int(row.student_id or 0) or None,
                'student_name': (student_map.get(int(row.student_id or 0)) or {}).get('student_name') or None,
                'batch_id': batch_id or None,
                'due_at': due_at.isoformat() if due_at else None,
                'overdue_minutes': overdue_minutes,
            }
        )
    return payload


def _risk_students(
    db: Session,
    *,
    center_id: int,
    teacher_batch_ids: set[int] | None,
) -> dict[str, list[dict]]:
    batch_filter = teacher_batch_ids if teacher_batch_ids is not None else None

    risk_query = (
        db.query(StudentRiskProfile, Student)
        .join(Student, Student.id == StudentRiskProfile.student_id)
        .filter(Student.center_id == center_id if center_id > 0 else True)
    )
    if batch_filter is not None:
        risk_query = risk_query.filter(Student.batch_id.in_(batch_filter))
    high_risk = [
        {
            'student_id': int(student.id),
            'student_name': str(student.name or ''),
            'risk_score': float(profile.final_risk_score or 0),
        }
        for profile, student in risk_query.filter(StudentRiskProfile.risk_level == 'HIGH').limit(20).all()
    ]

    today = default_time_provider.today()
    fee_query = (
        db.query(FeeRecord, Student)
        .join(Student, Student.id == FeeRecord.student_id)
        .filter(
            Student.center_id == center_id if center_id > 0 else True,
            FeeRecord.is_paid.is_(False),
            FeeRecord.due_date <= today,
        )
    )
    if batch_filter is not None:
        fee_query = fee_query.filter(Student.batch_id.in_(batch_filter))
    fee_overdue = []
    for fee, student in fee_query.limit(20).all():
        due_amount = max(0.0, float(fee.amount or 0) - float(fee.paid_amount or 0))
        if due_amount <= 0:
            continue
        fee_overdue.append(
            {
                'student_id': int(student.id),
                'student_name': str(student.name or ''),
                'amount_due': round(due_amount, 2),
            }
        )

    week_start = today - timedelta(days=7)
    attendance_query = (
        db.query(
            AttendanceRecord.student_id,
            func.count(AttendanceRecord.id).label('absent_count'),
        )
        .join(Student, Student.id == AttendanceRecord.student_id)
        .filter(
            Student.center_id == center_id if center_id > 0 else True,
            AttendanceRecord.attendance_date >= week_start,
            AttendanceRecord.attendance_date <= today,
            AttendanceRecord.status == 'Absent',
        )
    )
    if batch_filter is not None:
        attendance_query = attendance_query.filter(Student.batch_id.in_(batch_filter))
    attendance_rows = attendance_query.group_by(AttendanceRecord.student_id).having(func.count(AttendanceRecord.id) >= 2).limit(20).all()
    absent_ids = [int(student_id) for student_id, _ in attendance_rows]
    names_map = {
        int(student_id): str(name or '')
        for student_id, name in (
            db.query(Student.id, Student.name).filter(Student.id.in_(absent_ids)).all() if absent_ids else []
        )
    }
    repeat_absentees = [
        {
            'student_id': int(student_id),
            'student_name': names_map.get(int(student_id), ''),
            'absent_count': int(absent_count or 0),
        }
        for student_id, absent_count in attendance_rows
    ]

    return {
        'high_risk': high_risk,
        'fee_overdue': fee_overdue,
        'repeat_absentees': repeat_absentees,
    }


def _capacity_warnings(
    db: Session,
    *,
    role: str,
    user_id: int,
) -> list[dict]:
    capacity_rows = get_batch_capacity(
        db,
        actor_role=role,
        actor_user_id=user_id if role == 'teacher' else None,
    )
    warnings: list[dict] = []
    for row in capacity_rows:
        utilization = float(row.get('utilization_percentage') or 0)
        max_students = row.get('max_students')
        if max_students is None:
            continue
        if utilization < 90:
            continue
        warnings.append(
            {
                'batch_id': int(row.get('batch_id') or 0),
                'batch_name': str(row.get('name') or ''),
                'utilization_percentage': utilization,
                'available_seats': row.get('available_seats'),
                'severity': 'critical' if utilization >= 100 else 'warning',
            }
        )
    warnings.sort(key=lambda row: row['utilization_percentage'], reverse=True)
    return warnings[:12]


def _suggested_actions(*, next_class: dict | None, pending_count: int, risk_count: int, capacity_count: int) -> list[dict]:
    suggestions: list[dict] = []
    if next_class:
        suggestions.append(
            {
                'id': 'open_next_class',
                'label': 'Open attendance for next class',
                'cta': 'Open Attendance',
                'href': '/attendance',
                'priority': 'high',
            }
        )
    if pending_count > 0:
        suggestions.append(
            {
                'id': 'clear_pending',
                'label': f'Handle {pending_count} pending action(s)',
                'cta': 'Open Today View',
                'href': '/today',
                'priority': 'high',
            }
        )
    if risk_count > 0:
        suggestions.append(
            {
                'id': 'review_risk',
                'label': f'Review {risk_count} risk signal(s)',
                'cta': 'Open Risk Board',
                'href': '/risk',
                'priority': 'medium',
            }
        )
    if capacity_count > 0:
        suggestions.append(
            {
                'id': 'capacity_plan',
                'label': f'Address {capacity_count} capacity warning(s)',
                'cta': 'Open Time & Capacity',
                'href': '/time-capacity',
                'priority': 'medium',
            }
        )
    if not suggestions:
        suggestions.append(
            {
                'id': 'all_clear',
                'label': 'Everything looks healthy. Continue routine operations.',
                'cta': 'Open Dashboard',
                'href': '/dashboard',
                'priority': 'low',
            }
        )
    return suggestions


def get_operational_brain(
    db: Session,
    user: dict,
    *,
    bypass_cache: bool = False,
    time_provider: TimeProvider = default_time_provider,
) -> dict[str, Any]:
    role = str(user.get('role') or '').strip().lower()
    user_id = int(user.get('user_id') or 0)
    center_id = int(user.get('center_id') or 0)
    cache_token = _brain_cache_key(center_id=center_id, user_id=user_id, role=role)

    if not bypass_cache:
        cached = cache.get_cached(cache_token)
        if cached is not None:
            return cached

    teacher_batch_ids: set[int] | None = None
    center_name = ''
    if center_id > 0:
        center = db.query(Center).filter(Center.id == center_id).first()
        center_name = str(center.name or '') if center else ''
    if role == 'teacher':
        teacher_batch_ids = get_teacher_batch_ids(db, user_id, center_id=center_id)
        if not teacher_batch_ids:
            payload = {
                'generated_at': time_provider.now().replace(tzinfo=None).isoformat(),
                'next_upcoming_class': None,
                'timeline': [],
                'pending_inbox_actions': [],
                'risk_students': {'high_risk': [], 'fee_overdue': [], 'repeat_absentees': []},
                'capacity_warnings': [],
                'suggested_actions': _suggested_actions(next_class=None, pending_count=0, risk_count=0, capacity_count=0),
                'meta': {'role': role, 'center_id': center_id, 'center_name': center_name, 'user_id': user_id},
            }
            cache.set_cached(cache_token, payload, ttl=OPERATIONAL_BRAIN_TTL_SECONDS)
            return payload

    today_view = get_today_view(db, actor=user, time_provider=time_provider)
    timeline = list(today_view.get('today_classes') or [])
    now = time_provider.now().replace(tzinfo=None)
    next_class = _next_upcoming_class(timeline, now=now)

    pending_actions = _pending_inbox_actions(
        db,
        role=role,
        user_id=user_id,
        center_id=center_id,
        teacher_batch_ids=teacher_batch_ids,
    )
    risk_students = _risk_students(db, center_id=center_id, teacher_batch_ids=teacher_batch_ids)
    capacity_warnings = _capacity_warnings(db, role=role, user_id=user_id)

    risk_count = (
        len(risk_students.get('high_risk') or [])
        + len(risk_students.get('fee_overdue') or [])
        + len(risk_students.get('repeat_absentees') or [])
    )
    suggestions = _suggested_actions(
        next_class=next_class,
        pending_count=len(pending_actions),
        risk_count=risk_count,
        capacity_count=len(capacity_warnings),
    )

    payload = {
        'generated_at': now.isoformat(),
        'next_upcoming_class': next_class,
        'timeline': timeline,
        'pending_inbox_actions': pending_actions,
        'risk_students': risk_students,
        'capacity_warnings': capacity_warnings,
        'suggested_actions': suggestions,
        'meta': {'role': role, 'center_id': center_id, 'center_name': center_name, 'user_id': user_id},
    }
    cache.set_cached(cache_token, payload, ttl=OPERATIONAL_BRAIN_TTL_SECONDS)
    return payload
