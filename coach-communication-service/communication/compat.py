from __future__ import annotations

from communication.app_state import get_context


async def send_telegram_message(
    tenant_id: str,
    recipient_id: str,
    message: str,
    *,
    user_id: str = "legacy",
) -> dict[str, object]:
    """Backward compatibility wrapper for legacy Telegram-only code.

    The wrapper emits an event so older callers can keep their interface while
    the communication service remains provider-agnostic internally.
    """
    ctx = get_context()
    event = "legacy.telegram.send"
    await ctx.event_bus.emit(
        event,
        {
            "tenant_id": tenant_id,
            "event": event,
            "user_id": user_id,
            "payload": {
                "recipients": [recipient_id],
                "message": message,
                "critical": True,
                "student_name": "",
                "batch": "",
                "time": "",
            },
        },
    )
    return {"queued": True}
