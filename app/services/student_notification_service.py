from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.communication_gateway import send_event as gateway_send_event
from app.models import AuthUser, Parent, ParentStudentMap, Student
from app.services.comms_service import queue_telegram_by_chat_id
from app.services.rule_config_service import get_effective_rule_config


def resolve_student_notification_chat_id(db: Session, student: Student) -> str:
    direct_chat = str(student.telegram_chat_id or "").strip()
    if direct_chat:
        return direct_chat

    parent_links = db.query(ParentStudentMap).filter(ParentStudentMap.student_id == int(student.id)).all()
    parent_ids = [int(row.parent_id) for row in parent_links]
    if parent_ids:
        parent = db.query(Parent).filter(Parent.id.in_(parent_ids), Parent.telegram_chat_id != "").first()
        if parent and str(parent.telegram_chat_id or "").strip():
            return str(parent.telegram_chat_id).strip()

    phone = str(student.guardian_phone or "").strip()
    if phone:
        parent = db.query(Parent).filter(Parent.phone == phone).first()
        if parent and str(parent.telegram_chat_id or "").strip():
            return str(parent.telegram_chat_id).strip()
        auth_user = db.query(AuthUser).filter(AuthUser.phone == phone).first()
        if auth_user and str(auth_user.telegram_chat_id or "").strip():
            return str(auth_user.telegram_chat_id).strip()
    return ""


def notify_student(
    db: Session,
    *,
    student: Student,
    message: str,
    notification_type: str,
    critical: bool = False,
) -> bool:
    cfg = get_effective_rule_config(db, batch_id=student.batch_id)
    if not bool(cfg.get("enable_student_lifecycle_notifications", True)):
        return False
    chat_id = resolve_student_notification_chat_id(db, student)
    if not chat_id:
        return False
    if critical:
        result = gateway_send_event(
            notification_type or 'student.lifecycle.critical',
            {
                'db': db,
                'tenant_id': settings.communication_tenant_id,
                'user_id': str(student.id),
                'event_payload': {'student_id': int(student.id), 'kind': 'student_lifecycle'},
                'message': message,
                'channels': ['telegram'],
                'critical': True,
                'entity_type': 'student',
                'entity_id': int(student.id),
                'student_id': int(student.id),
                'notification_type': notification_type or '',
            },
            [{'chat_id': chat_id, 'user_id': str(student.id)}],
        )
        return bool(result and result[0].get('ok'))
    queue_telegram_by_chat_id(
        db,
        chat_id=chat_id,
        message=message,
        student_id=student.id,
        critical=critical,
        notification_type=notification_type,
    )
    return True
