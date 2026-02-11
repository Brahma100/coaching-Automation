from datetime import datetime
from sqlalchemy.orm import Session

from app.models import PendingAction
from app.services import snapshot_service


def create_pending_action(
    db: Session,
    action_type: str,
    student_id: int | None,
    related_session_id: int | None,
    note: str = '',
    teacher_id: int | None = None,
    session_id: int | None = None,
    due_at: datetime | None = None,
):
    session_id = session_id or related_session_id
    related_session_id = related_session_id or session_id
    existing = db.query(PendingAction).filter(
        PendingAction.action_type == action_type,
        PendingAction.student_id == student_id,
        PendingAction.session_id == session_id,
        PendingAction.teacher_id == teacher_id,
        PendingAction.status == 'open',
    ).first()
    if existing:
        return existing

    row = PendingAction(
        type=action_type,
        action_type=action_type,
        student_id=student_id,
        related_session_id=related_session_id,
        session_id=session_id,
        teacher_id=teacher_id,
        status='open',
        note=note,
        due_at=due_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    # CQRS-lite snapshots: best-effort refresh (never break the write path).
    try:
        if row.teacher_id:
            snapshot_service.refresh_teacher_today_snapshot(db, teacher_id=int(row.teacher_id))
        snapshot_service.refresh_admin_ops_snapshot(db)
    except Exception:
        pass
    return row


def list_open_actions(db: Session):
    return db.query(PendingAction).filter(PendingAction.status == 'open').order_by(PendingAction.created_at.desc()).all()


def resolve_action(db: Session, action_id: int, resolution_note: str | None = None):
    row = db.query(PendingAction).filter(PendingAction.id == action_id).first()
    if not row:
        raise ValueError('Pending action not found')
    row.status = 'resolved'
    row.resolved_at = datetime.utcnow()
    if resolution_note:
        row.resolution_note = resolution_note
    db.commit()
    db.refresh(row)

    # CQRS-lite snapshots: best-effort refresh (never break the write path).
    try:
        if row.teacher_id:
            snapshot_service.refresh_teacher_today_snapshot(db, teacher_id=int(row.teacher_id))
        snapshot_service.refresh_admin_ops_snapshot(db)
    except Exception:
        pass
    return row


def resolve_action_by_type(
    db: Session,
    *,
    action_type: str,
    teacher_id: int | None,
    session_id: int | None,
    student_id: int | None = None,
    resolution_note: str | None = None,
):
    row = db.query(PendingAction).filter(
        PendingAction.action_type == action_type,
        PendingAction.teacher_id == teacher_id,
        PendingAction.session_id == session_id,
        PendingAction.student_id == student_id,
        PendingAction.status == 'open',
    ).first()
    if not row:
        return None
    row.status = 'resolved'
    row.resolved_at = datetime.utcnow()
    if resolution_note:
        row.resolution_note = resolution_note
    db.commit()
    db.refresh(row)

    # CQRS-lite snapshots: best-effort refresh (never break the write path).
    try:
        if row.teacher_id:
            snapshot_service.refresh_teacher_today_snapshot(db, teacher_id=int(row.teacher_id))
        snapshot_service.refresh_admin_ops_snapshot(db)
    except Exception:
        pass
    return row
