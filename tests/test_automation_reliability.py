import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.domain.communication_gateway import send_event
from app.models import (
    AttendanceRecord,
    AutomationFailureLog,
    Batch,
    Center,
    ClassSession,
    CommunicationLog,
    Student,
)
from app.services.attendance_service import submit_attendance


class _AlwaysFailClient:
    def emit_event(self, *_args, **_kwargs):
        return {'queued': False}


class AutomationReliabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_automation_reliability.db'
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
            db.query(AutomationFailureLog).delete()
            db.query(AttendanceRecord).delete()
            db.query(ClassSession).delete()
            db.query(Student).delete()
            db.query(Batch).delete()
            db.query(CommunicationLog).delete()
            db.query(Center).delete()
            db.add(Center(id=1, name='Default', slug='default-center', timezone='UTC'))
            db.commit()
        finally:
            db.close()

    def test_failed_send_increments_attempts(self):
        db = self._session_factory()
        try:
            with patch('app.domain.communication_gateway.get_communication_client', return_value=_AlwaysFailClient()):
                result = send_event(
                    'test.event',
                    {'db': db, 'entity_type': 'class_session', 'entity_id': 101, 'message': 'hello', 'channels': ['telegram']},
                    [{'chat_id': 'chat-1'}],
                )
            self.assertEqual(result[0]['status'], 'failed')
            row = db.query(CommunicationLog).filter(CommunicationLog.event_type == 'test.event').first()
            self.assertIsNotNone(row)
            self.assertEqual(int(row.delivery_attempts), 1)
            self.assertEqual(row.delivery_status, 'failed')
            self.assertIsNotNone(row.last_attempt_at)
        finally:
            db.close()

    def test_retry_logic_retries_after_backoff(self):
        db = self._session_factory()
        try:
            with patch('app.domain.communication_gateway.get_communication_client', return_value=_AlwaysFailClient()):
                send_event(
                    'test.retry',
                    {'db': db, 'entity_type': 'class_session', 'entity_id': 102, 'message': 'hello', 'channels': ['telegram']},
                    [{'chat_id': 'chat-2'}],
                )
                row = db.query(CommunicationLog).filter(CommunicationLog.event_type == 'test.retry').first()
                row.last_attempt_at = datetime.utcnow() - timedelta(minutes=6)
                db.commit()
                send_event(
                    'test.retry',
                    {'db': db, 'entity_type': 'class_session', 'entity_id': 102, 'message': 'hello', 'channels': ['telegram']},
                    [{'chat_id': 'chat-2'}],
                )
            row = db.query(CommunicationLog).filter(CommunicationLog.event_type == 'test.retry').first()
            self.assertEqual(int(row.delivery_attempts), 2)
            self.assertEqual(row.delivery_status, 'failed')
        finally:
            db.close()

    def test_dead_letter_created_after_three_failures(self):
        db = self._session_factory()
        try:
            with patch('app.domain.communication_gateway.get_communication_client', return_value=_AlwaysFailClient()):
                send_event(
                    'test.deadletter',
                    {'db': db, 'entity_type': 'class_session', 'entity_id': 103, 'message': 'hello', 'channels': ['telegram']},
                    [{'chat_id': 'chat-3'}],
                )
                row = db.query(CommunicationLog).filter(CommunicationLog.event_type == 'test.deadletter').first()
                row.delivery_attempts = 2
                row.delivery_status = 'failed'
                row.last_attempt_at = datetime.utcnow() - timedelta(minutes=6)
                db.commit()
                result = send_event(
                    'test.deadletter',
                    {'db': db, 'entity_type': 'class_session', 'entity_id': 103, 'message': 'hello', 'channels': ['telegram']},
                    [{'chat_id': 'chat-3'}],
                )
            self.assertEqual(result[0]['status'], 'permanently_failed')
            failures = db.query(AutomationFailureLog).filter(AutomationFailureLog.job_name == 'communication_delivery').all()
            self.assertEqual(len(failures), 1)
        finally:
            db.close()

    def test_post_class_failure_does_not_rollback_attendance(self):
        db = self._session_factory()
        try:
            batch = Batch(id=11, name='Batch A', subject='Math', academic_level='10', center_id=1)
            student = Student(id=21, name='S1', batch_id=11, center_id=1)
            session = ClassSession(
                id=31,
                batch_id=11,
                subject='Math',
                scheduled_start=datetime.utcnow() - timedelta(hours=1),
                duration_minutes=60,
                teacher_id=0,
                center_id=1,
                status='open',
            )
            db.add_all([batch, student, session])
            db.commit()

            with patch('app.services.attendance_service.run_post_class_pipeline', side_effect=RuntimeError('pipeline down')):
                result = submit_attendance(
                    db=db,
                    batch_id=11,
                    attendance_date=session.scheduled_start.date(),
                    records=[{'student_id': 21, 'status': 'Present', 'comment': ''}],
                    class_session_id=31,
                    actor_role='admin',
                    actor_user_id=999,
                )

            self.assertEqual(result['updated_records'], 1)
            self.assertEqual(db.query(AttendanceRecord).count(), 1)
            refreshed = db.query(ClassSession).filter(ClassSession.id == 31).first()
            self.assertEqual(refreshed.status, 'submitted')
            self.assertTrue(bool(refreshed.post_class_error))
            self.assertIsNone(refreshed.post_class_processed_at)
            self.assertGreaterEqual(
                db.query(AutomationFailureLog).filter(AutomationFailureLog.job_name == 'post_class_pipeline').count(),
                1,
            )
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
