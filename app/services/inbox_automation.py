from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import AuthUser, Batch, ClassSession, PendingAction, Student
from app.services.comms_service import queue_teacher_telegram
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


def _session_end_time(session: ClassSession) -> datetime:
    return session.scheduled_start + timedelta(minutes=session.duration_minutes or 60)


def _parse_hhmm(value: str):
    hour, minute = value.split(':', 1)
    return int(hour), int(minute)


def _is_quiet_now_for_batch(db: Session, batch_id: int | None) -> bool:
    cfg = get_effective_rule_config(db, batch_id=batch_id)
    start_h, start_m = _parse_hhmm(cfg.get('quiet_hours_start', '22:00'))
    end_h, end_m = _parse_hhmm(cfg.get('quiet_hours_end', '06:00'))
    now = datetime.now().time()
    start_t = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end_t = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    if start_t <= end_t:
        return start_t <= now < end_t
    return now >= start_t or now < end_t


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
) -> list[int]:
    due_at = datetime.utcnow() + timedelta(hours=48)
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
    rows = (
        db.query(PendingAction)
        .filter(
            PendingAction.status == 'open',
            or_(PendingAction.teacher_id == teacher_id, PendingAction.teacher_id.is_(None)),
        )
        .order_by(PendingAction.due_at.asc().nulls_last(), PendingAction.created_at.desc())
        .all()
    )
    return rows


@timed_service('inbox_escalation')
def send_inbox_escalations(db: Session) -> dict:
    now = datetime.utcnow()
    rows = (
        db.query(PendingAction, ClassSession, Batch)
        .join(ClassSession, ClassSession.id == PendingAction.session_id, isouter=True)
        .join(Batch, Batch.id == ClassSession.batch_id, isouter=True)
        .filter(
            PendingAction.status == 'open',
            PendingAction.due_at.is_not(None),
            PendingAction.due_at < now,
            PendingAction.escalation_sent_at.is_(None),
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
        overdue_count = len(items)
        sample = items[:3]
        lines = [
            "⚠ Action Pending",
            f"You have {overdue_count} overdue task(s):",
        ]
        for action, session, batch in sample:
            if action.action_type == ACTION_REVIEW and batch:
                lines.append(f"- Review {batch.name} class summary")
            elif action.action_type == ACTION_ABSENTEE and session:
                student = db.query(Student).filter(Student.id == action.student_id).first()
                name = student.name if student else f"Student {action.student_id}"
                lines.append(f"- Follow up absentee: {name}")
            elif action.action_type == ACTION_FEE:
                student = db.query(Student).filter(Student.id == action.student_id).first()
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

        auth_user = db.query(AuthUser).filter(AuthUser.id == teacher_id).first()
        if not auth_user:
            continue
        chat_id = resolve_teacher_chat_id(db, auth_user.phone)
        if not chat_id:
            continue
        if _is_quiet_now_for_batch(db, batch_id=batch_id):
            logger.info('inbox_escalation_suppressed_quiet_hours', extra={'teacher_id': teacher_id})
            continue

        queue_teacher_telegram(
            db,
            teacher_id=teacher_id,
            chat_id=chat_id,
            message=message,
            batch_id=batch_id,
            critical=False,
            delete_at=None,
            notification_type='inbox_escalation',
            session_id=None,
        )

        for action, _, _ in items:
            action.escalation_sent_at = now
        db.commit()
        nudges += 1

    return {'inspected': inspected, 'nudges_sent': nudges}
