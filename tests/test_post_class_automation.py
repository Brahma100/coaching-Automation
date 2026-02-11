import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import Base
from app.models import (
    AllowedUser,
    AllowedUserStatus,
    AttendanceRecord,
    AuthUser,
    Batch,
    ClassSession,
    CommunicationLog,
    FeeRecord,
    RuleConfig,
    Student,
)
from app.services.post_class_automation_engine import run_post_class_automation


class PostClassAutomationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_post_class_automation.db'
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
            for table in (
                CommunicationLog,
                AttendanceRecord,
                FeeRecord,
                ClassSession,
                Student,
                Batch,
                AuthUser,
                AllowedUser,
                RuleConfig,
            ):
                db.query(table).delete()
            db.commit()
        finally:
            db.close()

    def _seed_base(self, db):
        rule = RuleConfig(
            batch_id=None,
            quiet_hours_start='00:00',
            quiet_hours_end='00:00',
        )
        db.add(rule)
        batch = Batch(name='Night Batch', subject='Math', academic_level='', active=True, start_time='23:00')
        db.add(batch)
        db.commit()
        db.refresh(batch)
        student_1 = Student(name='Alice', guardian_phone='1', telegram_chat_id='s1', batch_id=batch.id)
        student_2 = Student(name='Bob', guardian_phone='2', telegram_chat_id='s2', batch_id=batch.id)
        db.add_all([student_1, student_2])
        db.commit()
        auth = AuthUser(phone='9990000001', role='teacher', notification_delete_minutes=15)
        allowed = AllowedUser(phone='9990000001', role='teacher', status=AllowedUserStatus.ACTIVE.value)
        db.add_all([auth, allowed])
        db.commit()
        db.refresh(auth)
        session = ClassSession(
            batch_id=batch.id,
            subject='Math',
            scheduled_start=datetime.utcnow() - timedelta(minutes=90),
            duration_minutes=60,
            teacher_id=auth.id,
            status='submitted',
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return batch, session, student_1, student_2

    def test_post_class_engine_manual_submit(self):
        db = self._session_factory()
        try:
            batch, session, student_1, student_2 = self._seed_base(db)
            db.add_all(
                [
                    AttendanceRecord(student_id=student_1.id, attendance_date=session.scheduled_start.date(), status='Present'),
                    AttendanceRecord(student_id=student_2.id, attendance_date=session.scheduled_start.date(), status='Absent'),
                ]
            )
            db.commit()
            db.add(FeeRecord(student_id=student_1.id, due_date=session.scheduled_start.date(), amount=500, paid_amount=0, is_paid=False))
            db.commit()

            with patch('app.services.comms_service.send_telegram_message_with_id', return_value=(True, 111)):
                with patch('app.services.comms_service.send_telegram_message', return_value=True):
                    result = run_post_class_automation(db, session_id=session.id, trigger_source='manual_submit')

            self.assertIn('post_class_summary', result['notifications_sent'])
            teacher_logs = db.query(CommunicationLog).filter(
                CommunicationLog.teacher_id == session.teacher_id,
                CommunicationLog.notification_type == 'post_class_summary',
            ).all()
            self.assertEqual(len(teacher_logs), 1)
        finally:
            db.close()

    def test_post_class_engine_auto_close(self):
        db = self._session_factory()
        try:
            _, session, student_1, _ = self._seed_base(db)
            db.add(AttendanceRecord(student_id=student_1.id, attendance_date=session.scheduled_start.date(), status='Present'))
            db.commit()
            with patch('app.services.comms_service.send_telegram_message_with_id', return_value=(True, 111)):
                with patch('app.services.comms_service.send_telegram_message', return_value=True):
                    result = run_post_class_automation(db, session_id=session.id, trigger_source='auto_close')
            self.assertEqual(result['trigger_source'], 'auto_close')
        finally:
            db.close()

    def test_teacher_notification_sent_once(self):
        db = self._session_factory()
        try:
            _, session, student_1, _ = self._seed_base(db)
            db.add(AttendanceRecord(student_id=student_1.id, attendance_date=session.scheduled_start.date(), status='Absent'))
            db.commit()
            with patch('app.services.comms_service.send_telegram_message_with_id', return_value=(True, 111)):
                with patch('app.services.comms_service.send_telegram_message', return_value=True):
                    run_post_class_automation(db, session_id=session.id, trigger_source='manual_submit')
                    run_post_class_automation(db, session_id=session.id, trigger_source='manual_submit')
            teacher_logs = db.query(CommunicationLog).filter(
                CommunicationLog.teacher_id == session.teacher_id,
                CommunicationLog.notification_type == 'post_class_summary',
            ).all()
            self.assertEqual(len(teacher_logs), 1)
        finally:
            db.close()

    def test_student_notifications_sent(self):
        db = self._session_factory()
        try:
            _, session, student_1, student_2 = self._seed_base(db)
            db.add_all(
                [
                    AttendanceRecord(student_id=student_1.id, attendance_date=session.scheduled_start.date(), status='Present'),
                    AttendanceRecord(student_id=student_2.id, attendance_date=session.scheduled_start.date(), status='Late'),
                ]
            )
            db.commit()
            with patch('app.services.comms_service.send_telegram_message_with_id', return_value=(True, 111)):
                with patch('app.services.comms_service.send_telegram_message', return_value=True):
                    run_post_class_automation(db, session_id=session.id, trigger_source='manual_submit')
            student_logs = db.query(CommunicationLog).filter(CommunicationLog.student_id.is_not(None)).all()
            self.assertEqual(len(student_logs), 2)
        finally:
            db.close()

    def test_no_issues_suppresses_teacher_message(self):
        db = self._session_factory()
        try:
            _, session, student_1, student_2 = self._seed_base(db)
            db.add_all(
                [
                    AttendanceRecord(student_id=student_1.id, attendance_date=session.scheduled_start.date(), status='Present'),
                    AttendanceRecord(student_id=student_2.id, attendance_date=session.scheduled_start.date(), status='Present'),
                ]
            )
            db.commit()
            with patch('app.services.comms_service.send_telegram_message_with_id', return_value=(True, 111)):
                with patch('app.services.comms_service.send_telegram_message', return_value=True):
                    result = run_post_class_automation(db, session_id=session.id, trigger_source='manual_submit')
            self.assertIn('post_class_summary', result['notifications_suppressed'])
            teacher_logs = db.query(CommunicationLog).filter(
                CommunicationLog.teacher_id == session.teacher_id,
                CommunicationLog.notification_type == 'post_class_summary',
            ).all()
            self.assertEqual(len(teacher_logs), 0)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
