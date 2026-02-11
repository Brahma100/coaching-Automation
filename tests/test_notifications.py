import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import Base
from app.models import ActionToken, AllowedUser, AllowedUserStatus, AuthUser, Batch, ClassSession, CommunicationLog, Role
from app.services.action_token_service import verify_token
from app.services.comms_service import delete_due_telegram_messages, delete_telegram_message, queue_teacher_telegram
from app.services.teacher_notification_service import send_class_start_reminder


class NotificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_notifications.db'
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
            for table in (CommunicationLog, ActionToken, ClassSession, Batch, AuthUser, AllowedUser):
                db.query(table).delete()
            db.commit()
        finally:
            db.close()

    def test_auto_delete_marks_deleted(self):
        db = self._session_factory()
        try:
            row = CommunicationLog(
                teacher_id=1,
                channel='telegram',
                message='test',
                status='sent',
                telegram_message_id=123,
                telegram_chat_id='chat-1',
                delete_at=datetime.utcnow() - timedelta(minutes=1),
            )
            db.add(row)
            db.commit()

            with patch('app.services.comms_service.delete_telegram_message', return_value=True):
                result = delete_due_telegram_messages(db)
            self.assertEqual(result['deleted'], 1)
            refreshed = db.query(CommunicationLog).first()
            self.assertEqual(refreshed.status, 'deleted')
        finally:
            db.close()

    def test_auto_delete_ignores_future(self):
        db = self._session_factory()
        try:
            row = CommunicationLog(
                teacher_id=2,
                channel='telegram',
                message='future',
                status='sent',
                telegram_message_id=456,
                telegram_chat_id='chat-2',
                delete_at=datetime.utcnow() + timedelta(minutes=10),
            )
            db.add(row)
            db.commit()

            with patch('app.services.comms_service.delete_telegram_message', return_value=True):
                result = delete_due_telegram_messages(db)
            self.assertEqual(result['deleted'], 0)
            refreshed = db.query(CommunicationLog).first()
            self.assertEqual(refreshed.status, 'sent')
        finally:
            db.close()

    def test_auto_delete_handles_404(self):
        class _Resp:
            status_code = 404

        with patch('app.services.comms_service.httpx.post', return_value=_Resp()):
            ok = delete_telegram_message('chat-9', 999)
        self.assertTrue(ok)

    def test_review_token_expiry(self):
        db = self._session_factory()
        try:
            from app.services.action_token_service import create_action_token
            token = create_action_token(
                db,
                action_type='attendance_review',
                payload={'session_id': 1},
                ttl_minutes=1,
            )['token']
            row = db.query(ActionToken).first()
            row.expires_at = datetime.utcnow() - timedelta(minutes=1)
            db.commit()
            with self.assertRaises(ValueError):
                verify_token(db, token, expected_action_type='attendance_review')
        finally:
            db.close()

    def test_class_start_delete_at_before_start(self):
        db = self._session_factory()
        try:
            settings.auth_otp_fallback_chat_id = 'chat-1'
            batch = Batch(name='Test Batch', subject='Math', academic_level='', active=True, start_time='07:00')
            db.add(batch)
            db.commit()
            db.refresh(batch)

            session = ClassSession(
                batch_id=batch.id,
                subject='Math',
                scheduled_start=datetime.utcnow() + timedelta(minutes=20),
                duration_minutes=60,
                status='open',
            )
            db.add(session)
            db.commit()
            db.refresh(session)

            allowed = AllowedUser(phone='6291711111', role=Role.TEACHER.value, status=AllowedUserStatus.ACTIVE.value)
            db.add(allowed)
            db.commit()
            auth = AuthUser(phone='6291711111', role=Role.TEACHER.value, notification_delete_minutes=15)
            db.add(auth)
            db.commit()

            captured = {}

            def fake_queue_teacher_telegram(db, **kwargs):
                captured['delete_at'] = kwargs.get('delete_at')

            with patch('app.services.teacher_notification_service.queue_teacher_telegram', side_effect=fake_queue_teacher_telegram):
                send_class_start_reminder(db, session, schedule_id=None)

            self.assertIsNotNone(captured.get('delete_at'))
            self.assertLessEqual(captured['delete_at'], session.scheduled_start)
        finally:
            db.close()

    def test_teacher_notification_dedup_by_type(self):
        db = self._session_factory()
        try:
            with patch('app.services.comms_service.send_telegram_message_with_id', return_value=(True, 123)):
                queue_teacher_telegram(
                    db,
                    teacher_id=10,
                    chat_id='chat-1',
                    message='Class start',
                    critical=True,
                    notification_type='class_start',
                    session_id=42,
                )
                queue_teacher_telegram(
                    db,
                    teacher_id=10,
                    chat_id='chat-1',
                    message='Class start again',
                    critical=True,
                    notification_type='class_start',
                    session_id=42,
                )
            rows = db.query(CommunicationLog).filter(CommunicationLog.teacher_id == 10).all()
            self.assertEqual(len(rows), 1)
        finally:
            db.close()

    def test_teacher_notification_allows_multiple_types_per_session(self):
        db = self._session_factory()
        try:
            with patch('app.services.comms_service.send_telegram_message_with_id', return_value=(True, 123)):
                queue_teacher_telegram(
                    db,
                    teacher_id=11,
                    chat_id='chat-2',
                    message='Class start',
                    critical=True,
                    notification_type='class_start',
                    session_id=99,
                )
                queue_teacher_telegram(
                    db,
                    teacher_id=11,
                    chat_id='chat-2',
                    message='Attendance submitted',
                    critical=True,
                    notification_type='attendance_submitted',
                    session_id=99,
                )
            rows = db.query(CommunicationLog).filter(CommunicationLog.teacher_id == 11).all()
            self.assertEqual(len(rows), 2)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
