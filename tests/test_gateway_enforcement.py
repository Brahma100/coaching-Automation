import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.domain.jobs import daily_teacher_brief
from app.models import AllowedUser, AllowedUserStatus, AuthUser, CommunicationLog, Role


class GatewayEnforcementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_gateway_enforcement.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

    @classmethod
    def tearDownClass(cls):
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        db = self._session_factory()
        try:
            db.query(CommunicationLog).delete()
            db.query(AllowedUser).delete()
            db.query(AuthUser).delete()
            db.add(AllowedUser(phone='9000001234', role=Role.TEACHER.value, status=AllowedUserStatus.ACTIVE.value))
            db.add(AuthUser(id=77, phone='9000001234', role=Role.TEACHER.value, center_id=1, telegram_chat_id='chat-77'))
            db.commit()
        finally:
            db.close()

    def test_scheduled_job_uses_gateway(self):
        db = self._session_factory()
        try:
            def _fake_run_job(_label, task):
                task(db, 1)

            with patch('app.domain.jobs.daily_teacher_brief.run_job', side_effect=_fake_run_job):
                with patch('app.services.comms_service.gateway_send_event', return_value=[{'ok': True, 'status': 'sent'}]) as gateway_send:
                    daily_teacher_brief.execute()
        finally:
            db.close()
        self.assertTrue(gateway_send.called)

    def test_static_no_direct_provider_send_paths(self):
        root = Path(__file__).resolve().parents[1]
        blocked = [
            '_send_telegram_direct_http(',
            'send_telegram_message(',
            'https://api.telegram.org',
            'https://graph.facebook.com',
        ]
        # Exclude isolated provider diagnostics/config constants from this production-flow check.
        excluded = {
            'app/services/teacher_communication_settings_service.py',
            'app/config.py',
        }
        violations: list[str] = []
        for path in root.joinpath('app').rglob('*.py'):
            rel = path.relative_to(root).as_posix()
            if rel in excluded:
                continue
            text = path.read_text(encoding='utf-8')
            for token in blocked:
                if token in text:
                    violations.append(f'{rel}: contains {token!r}')
        self.assertEqual([], violations, '\n'.join(violations))


if __name__ == '__main__':
    unittest.main()
