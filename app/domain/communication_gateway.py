from __future__ import annotations

from datetime import timedelta
import logging

from sqlalchemy import or_

from app.communication.client_factory import get_communication_client
from app.config import settings
from app.domain.communication_guard import is_duplicate_send
from app.core.time_provider import default_time_provider
from app.models import CommunicationLog, ProviderCircuitState
from app.services.automation_failure_service import log_automation_failure
from app.services.center_scope_service import get_current_center_id
from app.services.rate_limit_service import SafeRateLimitError, check_rate_limit


logger = logging.getLogger(__name__)
__all__ = ['send_event']

CIRCUIT_FAILURE_WINDOW_SECONDS = 300
CIRCUIT_OPEN_THRESHOLD = 5
CIRCUIT_OPEN_SECONDS = 600


def _resolve_center_id(payload: dict) -> int:
    try:
        from_payload = int(payload.get('center_id') or 0)
    except Exception:
        from_payload = 0
    if from_payload > 0:
        return from_payload
    scoped = int(get_current_center_id() or 0)
    return scoped if scoped > 0 else 1


def _get_or_create_provider_state(db, *, center_id: int, provider_name: str, now):
    row = (
        db.query(ProviderCircuitState)
        .filter(
            ProviderCircuitState.center_id == int(center_id or 1),
            ProviderCircuitState.provider_name == str(provider_name or 'telegram'),
        )
        .with_for_update()
        .first()
    )
    if row is None:
        row = ProviderCircuitState(
            center_id=int(center_id or 1),
            provider_name=str(provider_name or 'telegram'),
            state='closed',
            failure_count=0,
            success_count=0,
            last_state_change_at=now,
        )
        db.add(row)
        db.flush()
    return row


def _circuit_allows_send(db, *, center_id: int, provider_name: str, now):
    state_row = _get_or_create_provider_state(
        db,
        center_id=int(center_id or 1),
        provider_name=str(provider_name or 'telegram'),
        now=now,
    )
    state = str(state_row.state or 'closed').lower()

    if state == 'open':
        changed_at = state_row.last_state_change_at or now
        if (now - changed_at).total_seconds() >= CIRCUIT_OPEN_SECONDS:
            state_row.state = 'half_open'
            state_row.success_count = 0
            state_row.last_state_change_at = now
            logger.warning(
                'circuit_transition_half_open',
                extra={'center_id': int(center_id or 1), 'provider': provider_name},
            )
            db.flush()
            return state_row, True
        return state_row, False

    if state == 'half_open':
        # Allow a single probe while half-open.
        if int(state_row.success_count or 0) > 0:
            return state_row, False
        return state_row, True

    return state_row, True


def _mark_circuit_failure(state_row: ProviderCircuitState, *, now):
    last_failure = state_row.last_failure_at
    if not last_failure or (now - last_failure).total_seconds() > CIRCUIT_FAILURE_WINDOW_SECONDS:
        state_row.failure_count = 1
    else:
        state_row.failure_count = int(state_row.failure_count or 0) + 1
    state_row.last_failure_at = now
    state_row.success_count = 0

    if str(state_row.state or 'closed').lower() == 'half_open':
        state_row.state = 'open'
        state_row.last_state_change_at = now
        logger.warning(
            'circuit_transition_open',
            extra={'center_id': int(state_row.center_id or 1), 'provider': state_row.provider_name},
        )
    elif int(state_row.failure_count or 0) >= CIRCUIT_OPEN_THRESHOLD:
        state_row.state = 'open'
        state_row.last_state_change_at = now
        logger.warning(
            'circuit_transition_open',
            extra={'center_id': int(state_row.center_id or 1), 'provider': state_row.provider_name},
        )


def _mark_circuit_success(state_row: ProviderCircuitState, *, now):
    state_row.failure_count = 0
    state_row.success_count = int(state_row.success_count or 0) + 1
    if str(state_row.state or 'closed').lower() != 'closed':
        state_row.state = 'closed'
        state_row.last_state_change_at = now
        logger.warning(
            'circuit_transition_closed',
            extra={'center_id': int(state_row.center_id or 1), 'provider': state_row.provider_name},
        )


def send_event(event_type, payload, recipients):
    """
    Unified communication gateway entrypoint.

    TODO: remove remaining legacy queue wrappers later.
    """
    data = payload or {}
    message = str(data.get('message') or '')
    reply_markup = data.get('reply_markup') if isinstance(data, dict) else None
    channels = data.get('channels') if isinstance(data, dict) else None
    preferred_providers = channels if isinstance(channels, list) and channels else ['telegram', 'whatsapp']
    tenant_id = data.get('tenant_id') if isinstance(data, dict) else None
    if not tenant_id:
        tenant_id = settings.communication_tenant_id
    db = data.get('db') if isinstance(data, dict) else None
    now = default_time_provider.now().replace(tzinfo=None)
    entity_id_raw = data.get('entity_id') if isinstance(data, dict) else None
    try:
        entity_id = int(entity_id_raw) if entity_id_raw is not None else 0
    except Exception:
        entity_id = 0
    retry_backoff_seconds = int(data.get('retry_backoff_seconds') or 300)
    max_attempts = int(data.get('max_delivery_attempts') or 3)
    entity_type = str(data.get('entity_type') or '')
    center_id = _resolve_center_id(data if isinstance(data, dict) else {})

    out: list[dict] = []
    for recipient in recipients or []:
        if isinstance(recipient, dict):
            chat_id = str(recipient.get('chat_id') or '').strip()
            user_id = str(recipient.get('user_id') or data.get('user_id') or 'system')
            receiver_id = str(recipient.get('receiver_id') or chat_id).strip()
        else:
            chat_id = str(recipient or '').strip()
            user_id = str(data.get('user_id') or 'system')
            receiver_id = chat_id

        if not chat_id:
            out.append({'ok': False, 'status': 'skipped', 'chat_id': chat_id, 'error': 'missing_chat_id'})
            continue
        if db is not None:
            try:
                check_rate_limit(
                    db,
                    center_id=center_id,
                    scope_type='center',
                    scope_key=str(center_id),
                    action_name='communication_send_event',
                    max_requests=100,
                    window_seconds=60,
                )
            except SafeRateLimitError:
                out.append({'ok': False, 'status': 'failed_backoff', 'chat_id': chat_id, 'message_id': None})
                continue

        delivery_log: CommunicationLog | None = None
        if db is not None and str(event_type or '').strip():
            delivery_log = (
                db.query(CommunicationLog)
                .filter(
                    CommunicationLog.event_type == str(event_type),
                    CommunicationLog.telegram_chat_id == chat_id,
                    or_(
                        CommunicationLog.reference_id == int(entity_id or 0),
                        CommunicationLog.session_id == int(entity_id or 0),
                        CommunicationLog.student_id == int(entity_id or 0),
                        CommunicationLog.teacher_id == int(entity_id or 0),
                    ),
                )
                .order_by(CommunicationLog.created_at.desc(), CommunicationLog.id.desc())
                .first()
            )

        if db is not None and entity_id > 0 and str(event_type or '').strip():
            if is_duplicate_send(
                db,
                event_type=str(event_type),
                entity_id=entity_id,
                receiver_id=receiver_id,
                window_seconds=300,
            ):
                if delivery_log is not None and delivery_log.delivery_status not in ('failed', 'pending'):
                    delivery_log.delivery_status = 'duplicate_suppressed'
                    db.commit()
                    out.append(
                        {
                            'ok': True,
                            'status': 'duplicate_suppressed',
                            'chat_id': chat_id,
                            'message_id': None,
                            'suppressed': True,
                            'log_id': int(delivery_log.id) if delivery_log is not None else None,
                        }
                    )
                    continue

        if delivery_log is None and db is not None:
            delivery_log = CommunicationLog(
                student_id=int(data.get('student_id') or 0) or None,
                teacher_id=int(data.get('teacher_id') or 0) or None,
                session_id=int(data.get('session_id') or 0) or None,
                channel='telegram',
                message=message,
                status='queued',
                telegram_chat_id=chat_id,
                notification_type=str(data.get('notification_type') or ''),
                event_type=str(event_type or ''),
                reference_id=int(data.get('reference_id') or entity_id or 0) or None,
                created_at=now,
                delivery_attempts=0,
                last_attempt_at=None,
                delivery_status='pending',
                delete_at=data.get('delete_at'),
            )
            db.add(delivery_log)
            db.commit()
            db.refresh(delivery_log)

        if delivery_log is not None and delivery_log.delivery_status == 'permanently_failed':
            out.append(
                {
                    'ok': False,
                    'status': 'permanently_failed',
                    'chat_id': chat_id,
                    'message_id': None,
                    'log_id': int(delivery_log.id),
                }
            )
            continue

        if delivery_log is not None and delivery_log.delivery_status in ('failed', 'failed_backoff'):
            last_attempt = delivery_log.last_attempt_at or delivery_log.created_at
            wait_seconds = (now - last_attempt).total_seconds()
            if int(delivery_log.delivery_attempts or 0) >= max_attempts:
                delivery_log.delivery_status = 'permanently_failed'
                db.commit()
                log_automation_failure(
                    db,
                    job_name='communication_delivery',
                    entity_type=entity_type or 'communication',
                    entity_id=entity_id if entity_id > 0 else delivery_log.id,
                    error_message='delivery retries exhausted',
                )
                db.commit()
                logger.error(
                    'automation_failure',
                    extra={
                        'job': 'communication_delivery',
                        'center_id': None,
                        'entity_id': entity_id,
                        'error': 'delivery retries exhausted',
                    },
                )
                out.append(
                    {
                        'ok': False,
                        'status': 'permanently_failed',
                        'chat_id': chat_id,
                        'message_id': None,
                        'log_id': int(delivery_log.id),
                    }
                )
                continue
            if wait_seconds < retry_backoff_seconds:
                out.append(
                    {
                        'ok': False,
                        'status': 'failed_backoff',
                        'chat_id': chat_id,
                        'message_id': None,
                        'log_id': int(delivery_log.id),
                    }
                )
                continue

        circuit_state = None
        selected_provider = str((preferred_providers or ['telegram'])[0] or 'telegram').strip().lower()
        if db is not None:
            circuit_state, allowed = _circuit_allows_send(
                db,
                center_id=center_id,
                provider_name=selected_provider,
                now=now,
            )
            if not allowed:
                logger.warning(
                    'provider_circuit_open_blocked_send',
                    extra={'center_id': int(center_id or 1), 'provider': selected_provider},
                )
                if delivery_log is not None:
                    delivery_log.delivery_status = 'failed_backoff'
                    delivery_log.status = 'failed_backoff'
                    db.commit()
                out.append(
                    {
                        'ok': False,
                        'status': 'failed_backoff',
                        'chat_id': chat_id,
                        'message_id': None,
                        'log_id': int(delivery_log.id) if delivery_log is not None else None,
                    }
                )
                continue

        if delivery_log is not None:
            delivery_log.delivery_attempts = int(delivery_log.delivery_attempts or 0) + 1
            delivery_log.last_attempt_at = now
            delivery_log.delivery_status = 'pending'
            db.commit()

        ok = False
        try:
            client = get_communication_client()
            response = client.emit_event(
                event_type,
                {
                    'tenant_id': tenant_id,
                    'user_id': user_id,
                    'payload': {
                        **(data.get('event_payload') or {}),
                        'message': message,
                        'recipients': [chat_id],
                        'preferred_providers': preferred_providers,
                        'priority': data.get('priority'),
                        'entity_type': data.get('entity_type'),
                        'entity_id': data.get('entity_id'),
                        'reply_markup': reply_markup or {},
                        'critical': bool(data.get('critical', False)),
                    },
                },
            )
            ok = bool(response.get('queued', False))
        except Exception as exc:
            logger.error(
                'automation_failure',
                extra={
                    'job': 'communication_emit',
                    'center_id': None,
                    'entity_id': entity_id,
                    'error': str(exc),
                },
            )

        status = 'sent' if ok else 'failed'
        if db is not None and circuit_state is not None:
            if ok:
                _mark_circuit_success(circuit_state, now=now)
            else:
                _mark_circuit_failure(circuit_state, now=now)
        if delivery_log is not None:
            delivery_log.delivery_status = status
            delivery_log.status = status
            if not ok and int(delivery_log.delivery_attempts or 0) >= max_attempts:
                delivery_log.delivery_status = 'permanently_failed'
                log_automation_failure(
                    db,
                    job_name='communication_delivery',
                    entity_type=entity_type or 'communication',
                    entity_id=entity_id if entity_id > 0 else delivery_log.id,
                    error_message='delivery retries exhausted',
                )
            db.commit()

        out.append(
            {
                'ok': bool(ok),
                'status': delivery_log.delivery_status if delivery_log is not None else status,
                'chat_id': chat_id,
                'message_id': None,
                'attempts': int(delivery_log.delivery_attempts) if delivery_log is not None else None,
                'log_id': int(delivery_log.id) if delivery_log is not None else None,
            }
        )
    return out
