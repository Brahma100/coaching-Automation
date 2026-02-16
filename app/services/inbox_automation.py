from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.communication.communication_event import CommunicationEvent, CommunicationEventType
from app.config import settings
from app.core.quiet_hours import is_quiet_now as _core_is_quiet_now
from app.core.time_provider import TimeProvider, default_time_provider
from app.models import AuthUser, Batch, ClassSession, PendingAction, Student
from app.services.automation_failure_service import log_automation_failure
from app.services.access_scope_service import get_teacher_batch_ids
from app.services.comms_service import emit_communication_event
from app.services.daily_teacher_brief_service import resolve_teacher_chat_id
from app.services.pending_action_service import create_pending_action, resolve_action, resolve_action_by_type
from app.services.rule_config_service import get_effective_rule_config
from app.metrics import timed_service


logger = logging.getLogger(__name__)


ACTION_REVIEW = 'review_session_summary'
ACTION_ABSENTEE = 'follow_up_absentee'
ACTION_FEE = 'follow_up_fee_due'
ACTION_ATTENDANCE_MISSED = 'attendance_missed'
ACTION_HOMEWORK = 'homework_not_reviewed'


def _warn_missing_center_filter(*, query_name: str) -> None:
    logger.warning('center_filter_missing service=inbox_automation query=%s', query_name)


def _resolve_teacher_batch_scope(db: Session, *, teacher_id: int, teacher_center_id: int) -> set[int]:
    if teacher_center_id <= 0:
        _warn_missing_center_filter(query_name='resolve_teacher_batch_scope_missing_center')
        return set()
    mapped = get_teacher_batch_ids(db, int(teacher_id or 0), center_id=teacher_center_id)
    if mapped:
        return mapped
    # Backward compatibility for tenants not yet configured with TeacherBatchMap.
    rows = (
        db.query(ClassSession.batch_id)
        .filter(
            ClassSession.teacher_id == int(teacher_id or 0),
            ClassSession.center_id == teacher_center_id,
        )
        .distinct()
        .all()
    )
    return {int(batch_id) for (batch_id,) in rows if batch_id is not None}


def _session_end_time(session: ClassSession) -> datetime:
    return session.scheduled_start + timedelta(minutes=session.duration_minutes or 60)


def _parse_hhmm(value: str):
    hour, minute = value.split(':', 1)
    return int(hour), int(minute)


def _is_quiet_now_for_batch(
    db: Session,
    batch_id: int | None,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> bool:
    # DEPRECATED: use app.core.quiet_hours.is_quiet_now directly.
    cfg = get_effective_rule_config(db, batch_id=batch_id)
    now = time_provider.local_now(settings.app_timezone).time()
    return _core_is_quiet_now(cfg, now)


def create_review_actions(
    db: Session,
    *,
    session: ClassSession,
    teacher_ids: list[int],
) -> list[int]:
    due_at = _session_end_time(session) + timedelta(hours=2)
    created = []
    for teacher_id in teacher_ids:
        row = create_pending_action(
            db,
            action_type=ACTION_REVIEW,
            student_id=None,
            related_session_id=session.id,
            note='Review session summary',
            teacher_id=teacher_id,
            session_id=session.id,
            due_at=due_at,
        )
        created.append(row.id)
    return created


def create_absentee_actions(
    db: Session,
    *,
    session: ClassSession,
    teacher_ids: list[int],
    absent_student_ids: list[int],
) -> list[int]:
    due_at = _session_end_time(session) + timedelta(hours=24)
    created = []
    for teacher_id in teacher_ids:
        for student_id in absent_student_ids:
            row = create_pending_action(
                db,
                action_type=ACTION_ABSENTEE,
                student_id=student_id,
                related_session_id=session.id,
                note='Follow up absentee',
                teacher_id=teacher_id,
                session_id=session.id,
                due_at=due_at,
            )
            created.append(row.id)
    return created


def create_fee_actions(
    db: Session,
    *,
    session: ClassSession,
    teacher_ids: list[int],
    student_ids: list[int],
    time_provider: TimeProvider = default_time_provider,
) -> list[int]:
    due_at = time_provider.now().replace(tzinfo=None) + timedelta(hours=48)
    created = []
    for teacher_id in teacher_ids:
        for student_id in student_ids:
            row = create_pending_action(
                db,
                action_type=ACTION_FEE,
                student_id=student_id,
                related_session_id=session.id,
                note='Follow up fee due',
                teacher_id=teacher_id,
                session_id=session.id,
                due_at=due_at,
            )
            created.append(row.id)
    return created


def resolve_review_action_on_open(db: Session, *, teacher_id: int, session_id: int) -> None:
    resolve_action_by_type(
        db,
        action_type=ACTION_REVIEW,
        teacher_id=teacher_id,
        session_id=session_id,
        resolution_note='Session summary opened',
    )


def resolve_fee_actions_on_paid(db: Session, *, student_id: int) -> int:
    rows = (
        db.query(PendingAction)
        .filter(
            PendingAction.action_type == ACTION_FEE,
            PendingAction.student_id == student_id,
            PendingAction.status == 'open',
        )
        .all()
    )
    resolved = 0
    for row in rows:
        resolve_action(db, row.id, resolution_note='Fee marked paid')
        resolved += 1
    return resolved


def list_inbox_actions(db: Session, *, teacher_id: int) -> list[PendingAction]:
    teacher_row = db.query(AuthUser).filter(AuthUser.id == int(teacher_id or 0)).first()
    teacher_center_id = int(teacher_row.center_id or 0) if teacher_row else 0
    if teacher_center_id <= 0:
        _warn_missing_center_filter(query_name='list_inbox_actions_missing_teacher_center')
        return []
    allowed_batch_ids = _resolve_teacher_batch_scope(db, teacher_id=int(teacher_id or 0), teacher_center_id=teacher_center_id)
    if not allowed_batch_ids:
        return []
    rows = (
        db.query(PendingAction)
        .filter(
            PendingAction.status == 'open',
            or_(PendingAction.teacher_id == teacher_id, PendingAction.teacher_id.is_(None)),
            PendingAction.center_id == teacher_center_id,
        )
        .order_by(PendingAction.due_at.asc().nulls_last(), PendingAction.created_at.desc())
        .all()
    )
    session_ids = {int(row.session_id or row.related_session_id or 0) for row in rows if (row.session_id or row.related_session_id)}
    student_ids = {int(row.student_id or 0) for row in rows if row.student_id}
    session_batch_map = {
        int(session_id): int(batch_id or 0)
        for session_id, batch_id in (
            db.query(ClassSession.id, ClassSession.batch_id)
            .filter(
                ClassSession.id.in_(session_ids),
                ClassSession.center_id == teacher_center_id,
            )
            .all()
        )
    } if session_ids else {}
    student_batch_map = {
        int(student_id): int(batch_id or 0)
        for student_id, batch_id in (
            db.query(Student.id, Student.batch_id)
            .filter(
                Student.id.in_(student_ids),
                Student.center_id == teacher_center_id,
            )
            .all()
        )
    } if student_ids else {}

    def _in_scope(action: PendingAction) -> bool:
        session_ref = int(action.session_id or action.related_session_id or 0)
        if session_ref:
            return int(session_batch_map.get(session_ref, 0)) in allowed_batch_ids
        if action.student_id:
            return int(student_batch_map.get(int(action.student_id), 0)) in allowed_batch_ids
        return False

    return [row for row in rows if _in_scope(row)]


@timed_service('inbox_escalation')
def send_inbox_escalations(
    db: Session,
    *,
    center_id: int,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    center_id = int(center_id or 0)
    if center_id <= 0:
        raise ValueError('center_id is required')
    now = time_provider.now().replace(tzinfo=None)
    rows = (
        db.query(PendingAction, ClassSession, Batch)
        .join(ClassSession, ClassSession.id == PendingAction.session_id, isouter=True)
        .join(Batch, Batch.id == ClassSession.batch_id, isouter=True)
        .filter(
            PendingAction.status == 'open',
            PendingAction.due_at.is_not(None),
            PendingAction.due_at < now,
            PendingAction.escalation_sent_at.is_(None),
            PendingAction.center_id == center_id,
            or_(ClassSession.id.is_(None), ClassSession.center_id == center_id),
            or_(Batch.id.is_(None), Batch.center_id == center_id),
        )
        .order_by(PendingAction.due_at.asc(), PendingAction.id.asc())
        .all()
    )
    if not rows:
        return {'inspected': 0, 'nudges_sent': 0}

    by_teacher: dict[int, list[tuple[PendingAction, ClassSession | None, Batch | None]]] = {}
    for action, session, batch in rows:
        if not action.teacher_id:
            continue
        by_teacher.setdefault(action.teacher_id, []).append((action, session, batch))

    nudges = 0
    inspected = len(rows)
    for teacher_id, items in by_teacher.items():
        teacher_row = db.query(AuthUser).filter(AuthUser.id == int(teacher_id or 0), AuthUser.center_id == center_id).first()
        teacher_center_id = int(teacher_row.center_id or 0) if teacher_row else 0
        items = [
            (action, session, batch)
            for action, session, batch in items
            if int(action.center_id or 0) == center_id
        ]
        allowed_batch_ids = _resolve_teacher_batch_scope(db, teacher_id=int(teacher_id or 0), teacher_center_id=teacher_center_id)
        if not allowed_batch_ids:
            continue
        scoped_items: list[tuple[PendingAction, ClassSession | None, Batch | None]] = []
        for action, session, batch in items:
            if session and int(session.batch_id or 0) in allowed_batch_ids:
                scoped_items.append((action, session, batch))
                continue
            if action.student_id:
                student_row = db.query(Student).filter(Student.id == action.student_id, Student.center_id == center_id).first()
                if student_row and int(student_row.batch_id or 0) in allowed_batch_ids:
                    scoped_items.append((action, session, batch))
        if not scoped_items:
            continue

        overdue_count = len(scoped_items)
        sample = scoped_items[:3]
        lines = [
            "⚠ Action Pending",
            f"You have {overdue_count} overdue task(s):",
        ]
        for action, session, batch in sample:
            if action.action_type == ACTION_REVIEW and batch:
                lines.append(f"- Review {batch.name} class summary")
            elif action.action_type == ACTION_ABSENTEE and session:
                student = db.query(Student).filter(Student.id == action.student_id, Student.center_id == center_id).first()
                name = student.name if student else f"Student {action.student_id}"
                lines.append(f"- Follow up absentee: {name}")
            elif action.action_type == ACTION_FEE:
                student = db.query(Student).filter(Student.id == action.student_id, Student.center_id == center_id).first()
                name = student.name if student else f"Student {action.student_id}"
                lines.append(f"- Follow up fee due: {name}")
            else:
                lines.append(f"- Pending action: {action.action_type}")
        lines.append("👉 Open Action Inbox")
        message = '\n'.join(lines)

        batch_id = None
        for _, session, _ in sample:
            if session and session.batch_id:
                batch_id = session.batch_id
                break

        auth_user = db.query(AuthUser).filter(AuthUser.id == teacher_id, AuthUser.center_id == center_id).first()
        if not auth_user:
            continue
        chat_id = resolve_teacher_chat_id(db, auth_user.phone)
        if not chat_id:
            continue
        if _is_quiet_now_for_batch(db, batch_id=batch_id, time_provider=time_provider):
            logger.info('inbox_escalation_suppressed_quiet_hours', extra={'teacher_id': teacher_id})
            continue

        delivery = emit_communication_event(
            db,
            CommunicationEvent(
                event_type=CommunicationEventType.DAILY_BRIEF.value,
                tenant_id=settings.communication_tenant_id,
                actor_id=teacher_id,
                entity_type='pending_action',
                entity_id=items[0][0].id,
                payload={'overdue_count': overdue_count, 'kind': 'inbox_escalation'},
                channels=['telegram'],
            ),
            message=message,
            chat_id=chat_id,
            teacher_id=teacher_id,
            batch_id=batch_id,
            critical=False,
            delete_at=None,
            notification_type='inbox_escalation',
            session_id=None,
            reference_id=items[0][0].id,
            time_provider=time_provider,
        )

        delivery_status = str((delivery or {}).get('status') or '')
        if delivery_status in ('sent', 'duplicate_suppressed'):
            for action, _, _ in scoped_items:
                action.escalation_sent_at = now
            db.commit()
            nudges += 1
            continue

        if delivery_status == 'permanently_failed':
            logger.error(
                'automation_failure',
                extra={
                    'job': 'inbox_escalation',
                    'center_id': teacher_center_id or 1,
                    'entity_id': int(items[0][0].id),
                    'error': 'delivery retries exhausted',
                },
            )
            log_automation_failure(
                db,
                job_name='inbox_escalation',
                entity_type='pending_action',
                entity_id=int(items[0][0].id),
                error_message='delivery retries exhausted',
                center_id=teacher_center_id or 1,
            )
            for action, _, _ in scoped_items:
                action.escalation_sent_at = now
            db.commit()
            continue

    return {'inspected': inspected, 'nudges_sent': nudges}
