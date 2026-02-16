import tempfile
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.domain.communication_gateway import send_event
from app.models import Center, ProviderCircuitState


class _FailingClient:
    def emit_event(self, event_type, payload):  # noqa: ARG002
        raise RuntimeError('provider unavailable')


class _SuccessClient:
    def emit_event(self, event_type, payload):  # noqa: ARG002
        return {'queued': True}


def _utc(y, m, d, hh=0, mm=0, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc)


def test_provider_circuit_breaker_transitions():
    tmpdir = tempfile.TemporaryDirectory()
    try:
        db_path = Path(tmpdir.name) / 'test_provider_circuit.db'
        engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        db = Session()
        try:
            db.add(Center(id=1, name='Center A', slug='center-a'))
            db.commit()

            payload = {
                'db': db,
                'center_id': 1,
                'entity_id': 111,
                'message': 'hello',
                'channels': ['whatsapp'],
                'retry_backoff_seconds': 1,
                'max_delivery_attempts': 10,
            }
            recipients = [{'chat_id': 'wa-user-1', 'receiver_id': 'receiver-1'}]

            base = _utc(2026, 2, 16, 10, 0, 0)
            tick = count()

            def _next_time():
                return base + timedelta(seconds=2 * next(tick))

            with patch('app.domain.communication_gateway.default_time_provider.now', side_effect=_next_time), patch(
                'app.domain.communication_gateway.get_communication_client',
                return_value=_FailingClient(),
            ):
                for _ in range(5):
                    send_event('provider_test', payload, recipients)

            state = (
                db.query(ProviderCircuitState)
                .filter(
                    ProviderCircuitState.center_id == 1,
                    ProviderCircuitState.provider_name == 'whatsapp',
                )
                .first()
            )
            assert state is not None
            assert state.state == 'open'
            attempts_before_open_block = 5

            # Circuit is open: send is skipped and attempts do not increase.
            with patch('app.domain.communication_gateway.default_time_provider.now', return_value=base + timedelta(minutes=1)), patch(
                'app.domain.communication_gateway.get_communication_client',
                return_value=_FailingClient(),
            ):
                blocked = send_event('provider_test', payload, recipients)
            assert blocked and blocked[0]['status'] == 'failed_backoff'
            state = db.query(ProviderCircuitState).filter(ProviderCircuitState.center_id == 1).first()
            assert state is not None and state.state == 'open'

            # Open timeout elapsed: half-open probe succeeds and closes circuit.
            with patch(
                'app.domain.communication_gateway.default_time_provider.now',
                return_value=base + timedelta(minutes=11),
            ), patch(
                'app.domain.communication_gateway.get_communication_client',
                return_value=_SuccessClient(),
            ):
                recovered = send_event('provider_test', payload, recipients)
            assert recovered and recovered[0]['status'] == 'sent'
            state = db.query(ProviderCircuitState).filter(ProviderCircuitState.center_id == 1).first()
            assert state is not None
            assert state.state == 'closed'
            assert state.failure_count == 0
            assert state.success_count >= 1

            # Verify attempt count behavior via latest communication log summary in response.
            assert int(recovered[0]['attempts']) == attempts_before_open_block + 1
        finally:
            db.close()
            engine.dispose()
    finally:
        tmpdir.cleanup()
