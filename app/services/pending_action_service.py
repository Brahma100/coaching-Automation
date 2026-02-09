from sqlalchemy.orm import Session

from app.models import PendingAction


def create_pending_action(
    db: Session,
    action_type: str,
    student_id: int | None,
    related_session_id: int | None,
    note: str = '',
):
    existing = db.query(PendingAction).filter(
        PendingAction.type == action_type,
        PendingAction.student_id == student_id,
        PendingAction.related_session_id == related_session_id,
        PendingAction.status == 'open',
    ).first()
    if existing:
        return existing

    row = PendingAction(
        type=action_type,
        student_id=student_id,
        related_session_id=related_session_id,
        status='open',
        note=note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_open_actions(db: Session):
    return db.query(PendingAction).filter(PendingAction.status == 'open').order_by(PendingAction.created_at.desc()).all()


def resolve_action(db: Session, action_id: int):
    row = db.query(PendingAction).filter(PendingAction.id == action_id).first()
    if not row:
        raise ValueError('Pending action not found')
    row.status = 'resolved'
    db.commit()
    db.refresh(row)
    return row
