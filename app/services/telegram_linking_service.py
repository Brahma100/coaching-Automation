from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.communication.client_factory import get_communication_client
from app.config import settings
from app.core.phone import normalize_phone as _core_normalize_phone
from app.domain.communication_gateway import send_event as gateway_send_event
from app.models import AuthUser, Parent, ParentStudentMap, Student, StudentBatchMap


logger = logging.getLogger(__name__)
_POLL_OFFSET: int | None = None


def extract_chat_and_text(update: dict[str, Any]) -> tuple[str, str]:
    msg = (update or {}).get("message") or (update or {}).get("edited_message") or {}
    chat = msg.get("chat") or {}
    chat_id = str(chat.get("id") or "").strip()
    text = str(msg.get("text") or "").strip()
    return chat_id, text


def _extract_contact(update: dict[str, Any]) -> dict[str, Any]:
    msg = (update or {}).get("message") or {}
    contact = msg.get("contact") or {}
    sender = msg.get("from") or {}
    return {
        "phone_number": str(contact.get("phone_number") or "").strip(),
        "contact_user_id": contact.get("user_id"),
        "from_user_id": sender.get("id"),
        "first_name": str(contact.get("first_name") or "").strip(),
        "last_name": str(contact.get("last_name") or "").strip(),
    }


def _normalize_phone(value: str) -> str:
    # DEPRECATED: use app.core.phone.normalize_phone directly.
    return _core_normalize_phone(value)


def _phone_candidates(value: str) -> list[str]:
    clean = _normalize_phone(value)
    if not clean:
        return []
    candidates: list[str] = [clean]
    # Common India formats from Telegram contacts/text:
    # +91XXXXXXXXXX, 91XXXXXXXXXX, 0XXXXXXXXXX
    if clean.startswith("91") and len(clean) > 10:
        candidates.append(clean[-10:])
    if clean.startswith("0") and len(clean) > 10:
        candidates.append(clean[-10:])
    if len(clean) > 10:
        candidates.append(clean[-10:])
    # Preserve order while removing duplicates.
    seen: set[str] = set()
    ordered: list[str] = []
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _send_linking_reply(
    db: Session,
    chat_id: str,
    message: str,
    reply_markup: dict[str, Any] | None = None,
) -> None:
    if not chat_id or not message:
        return
    gateway_send_event(
        'telegram_linking.reply',
        {
            'db': db,
            'tenant_id': settings.communication_tenant_id,
            'user_id': 'telegram_linking',
            'event_payload': {'channel': 'telegram_linking'},
            'message': message,
            'channels': ['telegram'],
            'critical': True,
            'entity_type': 'telegram_linking',
            'entity_id': 0,
            'notification_type': 'telegram_linking_reply',
            'reply_markup': reply_markup or {},
        },
        [{'chat_id': chat_id, 'user_id': 'telegram_linking'}],
    )


def _link_user_to_chat(db: Session, user: AuthUser, chat_id: str) -> None:
    others = db.query(AuthUser).filter(AuthUser.id != user.id, AuthUser.telegram_chat_id == chat_id).all()
    for row in others:
        row.telegram_chat_id = ""
    user.telegram_chat_id = chat_id
    parent = db.query(Parent).filter(Parent.phone == user.phone).first()
    if parent and not (parent.telegram_chat_id or "").strip():
        parent.telegram_chat_id = chat_id
    db.commit()


def _find_known_phone_matches(db: Session, phone: str, *, center_id: int) -> dict[str, Any]:
    candidates = _phone_candidates(phone)
    clean_phone = candidates[0] if candidates else _normalize_phone(phone)
    auth_users = db.query(AuthUser).filter(AuthUser.phone.in_(candidates), AuthUser.center_id == center_id).all() if candidates else []
    students = db.query(Student).filter(Student.guardian_phone.in_(candidates), Student.center_id == center_id).all() if candidates else []
    parents = db.query(Parent).filter(Parent.phone.in_(candidates), Parent.center_id == center_id).all() if candidates else []
    canonical_phone = (
        str(auth_users[0].phone)
        if auth_users
        else str(students[0].guardian_phone)
        if students
        else str(parents[0].phone)
        if parents
        else clean_phone
    )
    return {
        "phone": canonical_phone,
        "auth_users": auth_users,
        "students": students,
        "parents": parents,
        "known": bool(auth_users or students or parents),
    }


def _format_dt(value: datetime | None) -> str:
    if not value:
        return "N/A"
    return value.strftime("%d %b %Y")


def _build_student_sections(db: Session, students: list[Student]) -> str:
    if not students:
        return ""
    lines: list[str] = ["Student Details:"]
    shown = 0
    for student in students:
        if shown >= 3:
            break
        shown += 1
        joined_row = (
            db.query(StudentBatchMap)
            .filter(StudentBatchMap.student_id == student.id, StudentBatchMap.active.is_(True))
            .order_by(StudentBatchMap.joined_at.desc())
            .first()
        )
        if not joined_row:
            joined_row = (
                db.query(StudentBatchMap)
                .filter(StudentBatchMap.student_id == student.id)
                .order_by(StudentBatchMap.joined_at.desc())
                .first()
            )
        joined_text = _format_dt(joined_row.joined_at if joined_row else None)
        parent_links = db.query(ParentStudentMap).filter(ParentStudentMap.student_id == student.id).all()
        parent_ids = [row.parent_id for row in parent_links]
        parents = db.query(Parent).filter(Parent.id.in_(parent_ids)).all() if parent_ids else []
        if parents:
            parent_text = ", ".join(
                f"{p.name} ({p.phone})" if str(p.phone or "").strip() else p.name for p in parents[:2]
            )
        elif str(student.guardian_phone or "").strip():
            parent_text = f"Guardian ({student.guardian_phone})"
        else:
            parent_text = "N/A"
        batch_name = student.batch.name if getattr(student, "batch", None) and getattr(student.batch, "name", "") else "N/A"
        lines.extend(
            [
                f"- {student.name} (ID: {student.id})",
                f"  Batch: {batch_name}",
                f"  Joined: {joined_text}",
                f"  Parent: {parent_text}",
                f"  Contact: {student.guardian_phone or 'N/A'}",
                (
                    "  Preferences: "
                    f"digest={'on' if student.enable_daily_digest else 'off'}, "
                    f"homework={'on' if student.enable_homework_reminders else 'off'}, "
                    f"motivation={'on' if student.enable_motivation_messages else 'off'}"
                ),
            ]
        )
    if len(students) > shown:
        lines.append(f"- +{len(students) - shown} more student(s)")
    return "\n" + "\n".join(lines)


def _build_welcome_message(db: Session, phone: str, matches: dict[str, Any]) -> str:
    roles = sorted({str(row.role or "").lower() for row in matches.get("auth_users", []) if str(row.role or "").strip()})
    role_text = ", ".join(role.upper() for role in roles) if roles else "STUDENT"
    students = matches.get("students", [])
    student_suffix = _build_student_sections(db, students)
    return (
        f"Welcome to LearningMate. Your account is linked and ready for notifications.\n"
        f"Phone: {phone}\n"
        f"Role(s): {role_text}\n"
        f"Matched records: auth={len(matches.get('auth_users', []))}, students={len(students)}, parents={len(matches.get('parents', []))}"
        f"{student_suffix}"
    )


def _resolve_linked_phone_for_chat(db: Session, chat_id: str, *, center_id: int) -> str:
    clean_chat = str(chat_id or "").strip()
    if not clean_chat:
        return ""
    auth_user = db.query(AuthUser).filter(AuthUser.telegram_chat_id == clean_chat, AuthUser.center_id == center_id).first()
    if auth_user and str(auth_user.phone or "").strip():
        return str(auth_user.phone).strip()
    parent = db.query(Parent).filter(Parent.telegram_chat_id == clean_chat, Parent.center_id == center_id).first()
    if parent and str(parent.phone or "").strip():
        return str(parent.phone).strip()
    student = db.query(Student).filter(Student.telegram_chat_id == clean_chat, Student.center_id == center_id).first()
    if student and str(student.guardian_phone or "").strip():
        return str(student.guardian_phone).strip()
    return ""


def _link_phone_matches(db: Session, phone: str, chat_id: str, matches: dict[str, Any]) -> None:
    for row in db.query(AuthUser).filter(AuthUser.telegram_chat_id == chat_id, AuthUser.phone != phone).all():
        row.telegram_chat_id = ""
    for row in matches.get("auth_users", []):
        row.telegram_chat_id = chat_id
    for row in matches.get("students", []):
        row.telegram_chat_id = chat_id
    for row in matches.get("parents", []):
        row.telegram_chat_id = chat_id
    db.commit()


def resolve_bot_username() -> str:
    configured = str(settings.telegram_bot_username or "").strip().lstrip("@")
    if configured:
        return configured
    token = str(settings.telegram_bot_token or "").strip()
    if not token:
        return ""
    url = f"{settings.telegram_api_base}/bot{token}/getMe"
    try:
        response = httpx.get(url, timeout=8)
        if response.status_code != 200:
            return ""
        data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        if not isinstance(data, dict) or not data.get("ok"):
            return ""
        result = data.get("result") or {}
        return str(result.get("username") or "").strip().lstrip("@")
    except Exception:
        logger.exception("telegram_get_me_failed")
        return ""


def get_telegram_webhook_info() -> dict[str, Any]:
    token = str(settings.telegram_bot_token or "").strip()
    if not token:
        return {"ok": False, "reason": "missing_bot_token", "url": ""}
    url = f"{settings.telegram_api_base}/bot{token}/getWebhookInfo"
    try:
        response = httpx.get(url, timeout=8)
    except Exception:
        logger.exception("telegram_get_webhook_info_failed")
        return {"ok": False, "reason": "request_failed", "url": ""}
    if response.status_code != 200:
        return {"ok": False, "reason": f"http_{response.status_code}", "url": ""}
    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    if not isinstance(data, dict) or not data.get("ok"):
        return {"ok": False, "reason": "invalid_payload", "url": ""}
    result = data.get("result") or {}
    webhook_url = str(result.get("url") or "").strip()
    return {
        "ok": True,
        "url": webhook_url,
        "pending_update_count": int(result.get("pending_update_count") or 0),
        "last_error_message": str(result.get("last_error_message") or ""),
    }


def should_poll_telegram_updates() -> tuple[bool, str]:
    mode = str(settings.telegram_link_polling_mode or "auto").strip().lower()
    if mode == "on":
        return True, "forced_on"
    if mode == "off":
        return False, "forced_off"
    info = get_telegram_webhook_info()
    if not info.get("ok"):
        return True, f"auto_fallback_{info.get('reason', 'unknown')}"
    webhook_url = str(info.get("url") or "").strip()
    if webhook_url:
        return False, "auto_webhook_configured"
    return True, "auto_no_webhook"


def process_link_update(db: Session, update: dict[str, Any], *, center_id: int) -> dict[str, Any]:
    if not isinstance(update, dict):
        return {"ok": True, "linked": False, "reason": "invalid_update_payload"}

    chat_id, text = extract_chat_and_text(update)
    contact = _extract_contact(update)
    contact_phone = _normalize_phone(contact.get("phone_number") or "")
    if chat_id and contact_phone:
        contact_user_id = contact.get("contact_user_id")
        from_user_id = contact.get("from_user_id")
        if contact_user_id and from_user_id and str(contact_user_id) != str(from_user_id):
            _send_linking_reply(db, chat_id, "Please share your own phone number to continue linking.")
            return {"ok": True, "linked": False, "reason": "contact_not_self"}
        matches = _find_known_phone_matches(db, contact_phone, center_id=center_id)
        if not matches.get("known"):
            _send_linking_reply(db, chat_id, "Please connect with Admin for registration.")
            return {"ok": True, "linked": False, "reason": "phone_not_registered"}
        matched_phone = str(matches.get("phone") or contact_phone)
        _link_phone_matches(db, matched_phone, chat_id, matches)
        _send_linking_reply(db, chat_id, _build_welcome_message(db, matched_phone, matches))
        return {"ok": True, "linked": True, "reason": "contact_verified_linked", "phone": matched_phone}
    # Fallback: accept phone typed as plain text.
    text_phone = _normalize_phone(text)
    if chat_id and text_phone and len(text_phone) >= 10:
        matches = _find_known_phone_matches(db, text_phone, center_id=center_id)
        if not matches.get("known"):
            _send_linking_reply(db, chat_id, "Please connect with Admin for registration.")
            return {"ok": True, "linked": False, "reason": "phone_not_registered_text"}
        matched_phone = str(matches.get("phone") or text_phone)
        _link_phone_matches(db, matched_phone, chat_id, matches)
        _send_linking_reply(db, chat_id, _build_welcome_message(db, matched_phone, matches))
        return {"ok": True, "linked": True, "reason": "text_phone_linked", "phone": matched_phone}
    client = get_communication_client()
    result = client.consume_telegram_link_update(
        update=update,
        expected_tenant_id=settings.communication_tenant_id,
    )
    if not result.get("matched"):
        reason = str(result.get("reason", "ignored"))
        if chat_id and text.lower().startswith("/start"):
            linked_phone = _resolve_linked_phone_for_chat(db, chat_id, center_id=center_id)
            if linked_phone:
                matches = _find_known_phone_matches(db, linked_phone, center_id=center_id)
                _send_linking_reply(db, chat_id, _build_welcome_message(db, linked_phone, matches))
                return {"ok": True, "linked": True, "reason": "already_linked"}
            _send_linking_reply(
                db,
                chat_id,
                "Welcome to LearningMate. Please share your phone number to link your account.",
                reply_markup={
                    "keyboard": [[{"text": "Share phone number", "request_contact": True}]],
                    "resize_keyboard": True,
                    "one_time_keyboard": True,
                },
            )
        return {"ok": True, "linked": False, "reason": reason}

    user_id = int(result.get("user_id") or 0)
    phone = str(result.get("phone") or "").strip()
    chat_id = str(result.get("chat_id") or "").strip()
    if user_id <= 0 or not phone or not chat_id:
        if chat_id:
            _send_linking_reply(db, chat_id, "Link request is invalid or expired. Please retry from the app.")
        return {"ok": True, "linked": False, "reason": "invalid_link_payload"}

    user = db.query(AuthUser).filter(AuthUser.id == user_id, AuthUser.phone == phone, AuthUser.center_id == center_id).first()
    if not user:
        _send_linking_reply(db, chat_id, "We could not find your account for this link request. Please retry from the app.")
        return {"ok": True, "linked": False, "reason": "user_not_found"}

    matches = _find_known_phone_matches(db, phone, center_id=center_id)
    if matches.get("known"):
        _link_phone_matches(db, phone, chat_id, matches)
        _send_linking_reply(db, chat_id, _build_welcome_message(db, phone, matches))
    else:
        _link_user_to_chat(db, user, chat_id)
        _send_linking_reply(db, chat_id, "Welcome to LearningMate. Your account is linked and ready for notifications.")
    return {"ok": True, "linked": True}


def poll_telegram_updates_for_linking(db: Session, *, center_id: int) -> dict[str, Any]:
    center_id = int(center_id or 0)
    if center_id <= 0:
        raise ValueError('center_id is required')
    global _POLL_OFFSET
    token = str(settings.telegram_bot_token or "").strip()
    if not token:
        return {"ok": False, "reason": "missing_bot_token"}
    url = f"{settings.telegram_api_base}/bot{token}/getUpdates"
    params: dict[str, Any] = {"timeout": 0, "allowed_updates": '["message","edited_message"]'}
    if _POLL_OFFSET is not None:
        params["offset"] = _POLL_OFFSET

    try:
        response = httpx.get(url, params=params, timeout=10)
    except Exception:
        logger.exception("telegram_get_updates_failed")
        return {"ok": False, "reason": "request_failed"}
    if response.status_code != 200:
        return {"ok": False, "reason": f"http_{response.status_code}"}
    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    if not isinstance(data, dict) or not data.get("ok"):
        return {"ok": False, "reason": "invalid_payload"}

    rows = data.get("result") or []
    linked = 0
    processed = 0
    max_update_id: int | None = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        update_id = row.get("update_id")
        if isinstance(update_id, int):
            max_update_id = update_id if max_update_id is None else max(max_update_id, update_id)
        processed += 1
        outcome = process_link_update(db, row, center_id=center_id)
        if outcome.get("linked"):
            linked += 1
    if max_update_id is not None:
        _POLL_OFFSET = max_update_id + 1
    return {"ok": True, "processed": processed, "linked": linked}
