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
    PendingAction,
    RuleConfig,
    Student,
)
from app.services.inbox_automation import (
    ACTION_REVIEW,
    resolve_review_action_on_open,
    send_inbox_escalations,
)
from app.services.post_class_automation_engine import run_post_class_automation


class InboxAutomationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_inbox_automation.db'
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
                PendingAction,
                AttendanceRecord,
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
        batch = Batch(name='Batch A', subject='Math', academic_level='', active=True, start_time='09:00')
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
        settings.auth_otp_fallback_chat_id = 'chat-1'
        return session, student_1, student_2

    def test_action_created_after_post_class(self):
        db = self._session_factory()
        try:
            session, student_1, student_2 = self._seed_base(db)
            db.add_all(
                [
                    AttendanceRecord(student_id=student_1.id, attendance_date=session.scheduled_start.date(), status='Present'),
                    AttendanceRecord(student_id=student_2.id, attendance_date=session.scheduled_start.date(), status='Absent'),
                ]
            )
            db.commit()
            with patch('app.services.comms_service.send_telegram_message_with_id', return_value=(True, 111)):
                with patch('app.services.comms_service.send_telegram_message', return_value=True):
                    run_post_class_automation(db, session_id=session.id, trigger_source='manual_submit')
            review_actions = db.query(PendingAction).filter(
                PendingAction.action_type == ACTION_REVIEW,
                PendingAction.session_id == session.id,
            ).all()
            self.assertEqual(len(review_actions), 1)
        finally:
            db.close()

    def test_no_duplicate_actions(self):
        db = self._session_factory()
        try:
            session, student_1, _ = self._seed_base(db)
            db.add(AttendanceRecord(student_id=student_1.id, attendance_date=session.scheduled_start.date(), status='Absent'))
            db.commit()
            with patch('app.services.comms_service.send_telegram_message_with_id', return_value=(True, 111)):
                with patch('app.services.comms_service.send_telegram_message', return_value=True):
                    run_post_class_automation(db, session_id=session.id, trigger_source='manual_submit')
                    run_post_class_automation(db, session_id=session.id, trigger_source='manual_submit')
            review_actions = db.query(PendingAction).filter(
                PendingAction.action_type == ACTION_REVIEW,
                PendingAction.session_id == session.id,
            ).all()
            self.assertEqual(len(review_actions), 1)
        finally:
            db.close()

    def test_escalation_sent_once(self):
        db = self._session_factory()
        try:
            session, student_1, _ = self._seed_base(db)
            action = PendingAction(
                action_type=ACTION_REVIEW,
                type=ACTION_REVIEW,
                teacher_id=session.teacher_id,
                session_id=session.id,
                student_id=None,
                status='open',
                due_at=datetime.utcnow() - timedelta(hours=1),
            )
            db.add(action)
            db.commit()

            with patch('app.services.comms_service.send_telegram_message_with_id', return_value=(True, 111)):
                send_inbox_escalations(db)
                send_inbox_escalations(db)

            logs = db.query(CommunicationLog).filter(
                CommunicationLog.notification_type == 'inbox_escalation'
            ).all()
            self.assertEqual(len(logs), 1)
        finally:
            db.close()

    def test_resolution_auto_closes_action(self):
        db = self._session_factory()
        try:
            session, _, _ = self._seed_base(db)
            action = PendingAction(
                action_type=ACTION_REVIEW,
                type=ACTION_REVIEW,
                teacher_id=session.teacher_id,
                session_id=session.id,
                status='open',
            )
            db.add(action)
            db.commit()
            resolve_review_action_on_open(db, teacher_id=session.teacher_id, session_id=session.id)
            refreshed = db.query(PendingAction).filter(PendingAction.id == action.id).first()
            self.assertEqual(refreshed.status, 'resolved')
        finally:
            db.close()

    def test_quiet_hours_suppress_escalation(self):
        db = self._session_factory()
        try:
            session, _, _ = self._seed_base(db)
            row = db.query(RuleConfig).first()
            row.quiet_hours_start = '00:00'
            row.quiet_hours_end = '23:59'
            db.commit()

            action = PendingAction(
                action_type=ACTION_REVIEW,
                type=ACTION_REVIEW,
                teacher_id=session.teacher_id,
                session_id=session.id,
                status='open',
                due_at=datetime.utcnow() - timedelta(hours=1),
            )
            db.add(action)
            db.commit()

            with patch('app.services.comms_service.send_telegram_message_with_id', return_value=(True, 111)):
                send_inbox_escalations(db)

            refreshed = db.query(PendingAction).filter(PendingAction.id == action.id).first()
            self.assertIsNone(refreshed.escalation_sent_at)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
