import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import (
    AttendanceRecord,
    AuthUser,
    Batch,
    BatchSchedule,
    ClassSession,
    CommunicationLog,
    FeeRecord,
    PendingAction,
    Student,
    StudentRiskEvent,
    StudentRiskProfile,
)
from app.services.admin_ops_dashboard_service import clear_admin_ops_cache, get_admin_ops_dashboard


class AdminOpsDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_admin_ops.db'
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
            clear_admin_ops_cache()
            for table in (
                CommunicationLog,
                PendingAction,
                AttendanceRecord,
                FeeRecord,
                ClassSession,
                BatchSchedule,
                Batch,
                StudentRiskEvent,
                StudentRiskProfile,
                Student,
                AuthUser,
            ):
                db.query(table).delete()
            db.commit()
        finally:
            db.close()

    def _seed_teacher(self, db, phone='9990000001'):
        teacher = AuthUser(phone=phone, role='teacher')
        db.add(teacher)
        db.commit()
        db.refresh(teacher)
        return teacher

    def test_admin_ops_system_alerts(self):
        db = self._session_factory()
        try:
            now = datetime(2026, 2, 10, 12, 0, 0)
            teacher = self._seed_teacher(db)
            overdue = PendingAction(
                type='follow_up_fee_due',
                action_type='follow_up_fee_due',
                teacher_id=teacher.id,
                status='open',
                due_at=now - timedelta(hours=30),
            )
            db.add(overdue)

            batch = Batch(name='Batch A', subject='Math', academic_level='', active=True, start_time='09:00')
            db.add(batch)
            db.commit()
            schedule = BatchSchedule(batch_id=batch.id, weekday=(now.date() - timedelta(days=1)).weekday(), start_time='09:00', duration_minutes=60)
            db.add(schedule)

            db.add(
                CommunicationLog(
                    notification_type='student_daily_digest',
                    status='failed',
                    channel='telegram',
                    message='fail',
                    created_at=now - timedelta(hours=2),
                )
            )
            db.commit()

            payload = get_admin_ops_dashboard(db, center_id=1, now=now)
            ids = {alert['id'] for alert in payload['system_alerts']}
            self.assertIn('overdue_actions', ids)
            self.assertIn('attendance_missing', ids)
            self.assertTrue(any('automation_failed' in alert_id for alert_id in ids))
        finally:
            db.close()

    def test_admin_ops_teacher_bottlenecks(self):
        db = self._session_factory()
        try:
            now = datetime(2026, 2, 10, 12, 0, 0)
            teacher = self._seed_teacher(db)
            batch = Batch(name='Batch T', subject='Math', academic_level='', active=True, start_time='09:00')
            db.add(batch)
            db.commit()
            db.refresh(batch)
            db.add(
                PendingAction(
                    type='review_session_summary',
                    action_type='review_session_summary',
                    teacher_id=teacher.id,
                    status='open',
                    due_at=now - timedelta(hours=2),
                )
            )
            db.add(
                PendingAction(
                    type='follow_up_absentee',
                    action_type='follow_up_absentee',
                    teacher_id=teacher.id,
                    status='open',
                    due_at=now + timedelta(hours=3),
                )
            )
            db.add(
                ClassSession(
                    batch_id=batch.id,
                    subject='Math',
                    scheduled_start=datetime.combine((now - timedelta(days=1)).date(), datetime.strptime('09:00', '%H:%M').time()),
                    duration_minutes=60,
                    status='missed',
                    teacher_id=teacher.id,
                )
            )
            db.commit()

            payload = get_admin_ops_dashboard(db, center_id=1, now=now)
            self.assertEqual(len(payload['teacher_bottlenecks']), 1)
            row = payload['teacher_bottlenecks'][0]
            self.assertEqual(row['open_actions'], 2)
            self.assertEqual(row['overdue_actions'], 1)
            self.assertEqual(row['classes_missed'], 1)
        finally:
            db.close()

    def test_admin_ops_batch_health(self):
        db = self._session_factory()
        try:
            now = datetime(2026, 2, 10, 12, 0, 0)
            batch = Batch(name='Batch B', subject='Science', academic_level='', active=True, start_time='10:00')
            db.add(batch)
            db.commit()
            db.refresh(batch)
            schedule = BatchSchedule(batch_id=batch.id, weekday=now.date().weekday(), start_time='10:00', duration_minutes=60)
            db.add(schedule)
            student = Student(name='Alice', guardian_phone='1', telegram_chat_id='s1', batch_id=batch.id)
            db.add(student)
            db.commit()
            db.refresh(student)

            db.add(
                ClassSession(
                    batch_id=batch.id,
                    subject='Science',
                    scheduled_start=datetime.combine(now.date(), datetime.strptime('10:00', '%H:%M').time()),
                    duration_minutes=60,
                    status='submitted',
                    teacher_id=1,
                )
            )
            db.add(
                AttendanceRecord(
                    student_id=student.id,
                    attendance_date=now.date() - timedelta(days=1),
                    status='Absent',
                )
            )
            db.add(
                AttendanceRecord(
                    student_id=student.id,
                    attendance_date=now.date() - timedelta(days=2),
                    status='Absent',
                )
            )
            db.add(
                FeeRecord(
                    student_id=student.id,
                    due_date=now.date(),
                    amount=500,
                    paid_amount=0,
                    is_paid=False,
                )
            )
            db.commit()

            payload = get_admin_ops_dashboard(db, center_id=1, now=now)
            self.assertEqual(len(payload['batch_health']), 1)
            row = payload['batch_health'][0]
            self.assertEqual(row['batch_id'], batch.id)
            self.assertEqual(row['fee_due_students'], 1)
            self.assertEqual(row['repeat_no_show_students'], 1)
            self.assertEqual(row['attendance_completion_rate'], 100.0)
        finally:
            db.close()

    def test_admin_ops_automation_health(self):
        db = self._session_factory()
        try:
            now = datetime(2026, 2, 10, 12, 0, 0)
            db.add(
                CommunicationLog(
                    notification_type='student_daily_digest',
                    status='sent',
                    channel='telegram',
                    message='digest',
                    created_at=now - timedelta(hours=2),
                )
            )
            db.add(
                CommunicationLog(
                    notification_type='inbox_escalation',
                    status='sent',
                    channel='telegram',
                    message='escalate',
                    created_at=now - timedelta(hours=3),
                )
            )
            db.commit()

            payload = get_admin_ops_dashboard(db, center_id=1, now=now)
            items = {item['key']: item for item in payload['automation_health']['items']}
            self.assertEqual(items['student_daily_digest']['status'], 'ok')
            self.assertEqual(items['inbox_escalation']['status'], 'stale')
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
