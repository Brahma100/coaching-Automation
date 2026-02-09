from app.config import settings
from app.services.action_token_service import create_action_token


def _action_url(endpoint_path: str, token: str) -> str:
    return f"{settings.app_base_url}{endpoint_path}?token={token}"


def build_inline_actions_for_student(
    db,
    student_id: int,
    parent_id: int | None = None,
    fee_record_id: int | None = None,
    pending_action_id: int | None = None,
):
    actions = []

    if parent_id:
        t = create_action_token(
            db,
            action_type='notify-parent',
            payload={'student_id': student_id, 'parent_id': parent_id, 'pending_action_id': pending_action_id},
            ttl_minutes=60,
        )
        actions.append({'text': 'Notify Parent', 'url': _action_url('/actions/notify-parent', t['token'])})

    t = create_action_token(
        db,
        action_type='send-fee-reminder',
        payload={'student_id': student_id, 'fee_record_id': fee_record_id, 'pending_action_id': pending_action_id},
        ttl_minutes=60,
    )
    actions.append({'text': 'Send Fee Reminder', 'url': _action_url('/actions/send-fee-reminder', t['token'])})

    t = create_action_token(
        db,
        action_type='escalate-student',
        payload={'student_id': student_id, 'pending_action_id': pending_action_id},
        ttl_minutes=60,
    )
    actions.append({'text': 'Escalate Student', 'url': _action_url('/actions/escalate-student', t['token'])})

    if pending_action_id:
        t = create_action_token(
            db,
            action_type='mark-resolved',
            payload={'pending_action_id': pending_action_id, 'student_id': student_id},
            ttl_minutes=60,
        )
        actions.append({'text': 'Mark Resolved', 'url': _action_url('/actions/mark-resolved', t['token'])})

    return {
        'inline_keyboard': [
            [actions[0]],
            [actions[1]],
            [actions[2]],
        ] + ([[actions[3]]] if len(actions) > 3 else []),
    }
