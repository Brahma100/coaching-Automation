import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AttendanceRecord, ClassSession, CommunicationLog, Homework, RuleConfig, Student
from app.services.student_automation_engine import (
    send_daily_digest,
    send_homework_due_tomorrow,
    send_student_attendance_feedback,
    send_weekly_motivation,
)


class StudentAutomationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_student_automation.db'
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
            for table in (CommunicationLog, AttendanceRecord, ClassSession, Homework, Student, RuleConfig):
                db.query(table).delete()
            db.commit()
            rule = RuleConfig(batch_id=None, quiet_hours_start='00:00', quiet_hours_end='00:00')
            db.add(rule)
            db.commit()
        finally:
            db.close()

    def test_student_attendance_message(self):
        db = self._session_factory()
        try:
            student = Student(name='A', guardian_phone='1', telegram_chat_id='chat-1', batch_id=1)
            db.add(student)
            db.commit()
            db.refresh(student)
            session = ClassSession(
                batch_id=1,
                subject='Math',
                scheduled_start=datetime.utcnow(),
                duration_minutes=60,
                status='submitted',
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            db.add(AttendanceRecord(student_id=student.id, attendance_date=session.scheduled_start.date(), status='Present'))
            db.commit()
            with patch('app.services.comms_service.send_telegram_message', return_value=True):
                send_student_attendance_feedback(db, session_id=session.id)
            logs = db.query(CommunicationLog).filter(
                CommunicationLog.student_id == student.id,
                CommunicationLog.notification_type == 'student_attendance',
                CommunicationLog.session_id == session.id,
            ).all()
            self.assertEqual(len(logs), 1)
        finally:
            db.close()

    def test_daily_digest_sent_only_when_needed(self):
        db = self._session_factory()
        try:
            student = Student(name='B', guardian_phone='2', telegram_chat_id='chat-2', batch_id=1)
            db.add(student)
            db.commit()
            with patch('app.services.comms_service.send_telegram_message', return_value=True):
                send_daily_digest(db)
            logs = db.query(CommunicationLog).filter(CommunicationLog.student_id == student.id).all()
            self.assertEqual(len(logs), 0)
            db.add(AttendanceRecord(student_id=student.id, attendance_date=date.today(), status='Present'))
            db.commit()
            with patch('app.services.comms_service.send_telegram_message', return_value=True):
                send_daily_digest(db)
            logs = db.query(CommunicationLog).filter(
                CommunicationLog.student_id == student.id,
                CommunicationLog.notification_type == 'student_daily_digest',
            ).all()
            self.assertEqual(len(logs), 1)
        finally:
            db.close()

    def test_homework_reminder(self):
        db = self._session_factory()
        try:
            student = Student(name='C', guardian_phone='3', telegram_chat_id='chat-3', batch_id=1)
            db.add(student)
            hw = Homework(title='HW1', description='Test', due_date=date.today() + timedelta(days=1))
            db.add(hw)
            db.commit()
            with patch('app.services.comms_service.send_telegram_message', return_value=True):
                send_homework_due_tomorrow(db)
            logs = db.query(CommunicationLog).filter(
                CommunicationLog.student_id == student.id,
                CommunicationLog.notification_type == 'homework_due_reminder',
                CommunicationLog.reference_id == hw.id,
            ).all()
            self.assertEqual(len(logs), 1)
        finally:
            db.close()

    def test_weekly_motivation_rate_limit(self):
        db = self._session_factory()
        try:
            student = Student(name='D', guardian_phone='4', telegram_chat_id='chat-4', batch_id=1)
            db.add(student)
            db.commit()
            for i in range(5):
                db.add(AttendanceRecord(student_id=student.id, attendance_date=date.today() - timedelta(days=i), status='Present'))
            db.commit()
            with patch('app.services.comms_service.send_telegram_message', return_value=True):
                send_weekly_motivation(db)
                send_weekly_motivation(db)
            logs = db.query(CommunicationLog).filter(
                CommunicationLog.student_id == student.id,
                CommunicationLog.notification_type == 'student_motivation_weekly',
            ).all()
            self.assertEqual(len(logs), 1)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
