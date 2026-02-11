import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import (
    ActionToken,
    AttendanceRecord,
    AuthUser,
    Batch,
    BatchSchedule,
    ClassSession,
    FeeRecord,
    PendingAction,
    Student,
    StudentRiskProfile,
)
from app.services.dashboard_today_service import clear_today_view_cache, get_today_view


class TodayViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_today_view.db'
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
            clear_today_view_cache()
            for table in (
                ActionToken,
                PendingAction,
                AttendanceRecord,
                FeeRecord,
                ClassSession,
                BatchSchedule,
                Batch,
                StudentRiskProfile,
                Student,
                AuthUser,
            ):
                db.query(table).delete()
            db.commit()
        finally:
            db.close()

    def _seed_teacher(self, db):
        teacher = AuthUser(phone='9990000001', role='teacher')
        db.add(teacher)
        db.commit()
        db.refresh(teacher)
        return teacher

    def test_today_view_overdue_actions(self):
        db = self._session_factory()
        try:
            teacher = self._seed_teacher(db)
            action = PendingAction(
                type='review_session_summary',
                action_type='review_session_summary',
                teacher_id=teacher.id,
                status='open',
                due_at=datetime.utcnow() - timedelta(hours=3),
            )
            db.add(action)
            db.commit()
            result = get_today_view(db, actor={'user_id': teacher.id, 'role': 'teacher'})
            self.assertEqual(len(result['overdue_actions']), 1)
        finally:
            db.close()

    def test_today_view_due_today(self):
        db = self._session_factory()
        try:
            teacher = self._seed_teacher(db)
            now = datetime.now()
            day_end = datetime.combine(now.date(), datetime.max.time())
            due_at = now + timedelta(minutes=10)
            if due_at > day_end:
                due_at = day_end - timedelta(minutes=1)
            action = PendingAction(
                type='follow_up_fee_due',
                action_type='follow_up_fee_due',
                teacher_id=teacher.id,
                status='open',
                due_at=due_at,
            )
            db.add(action)
            db.commit()
            result = get_today_view(db, actor={'user_id': teacher.id, 'role': 'teacher'})
            self.assertEqual(len(result['due_today_actions']), 1)
        finally:
            db.close()

    def test_today_view_classes(self):
        db = self._session_factory()
        try:
            teacher = self._seed_teacher(db)
            batch = Batch(name='Batch A', subject='Math', academic_level='', active=True, start_time='09:00')
            db.add(batch)
            db.commit()
            db.refresh(batch)
            schedule = BatchSchedule(batch_id=batch.id, weekday=date.today().weekday(), start_time='09:00', duration_minutes=60)
            db.add(schedule)
            db.commit()
            session = ClassSession(
                batch_id=batch.id,
                subject='Math',
                scheduled_start=datetime.combine(date.today(), datetime.strptime('09:00', '%H:%M').time()),
                duration_minutes=60,
                status='submitted',
                teacher_id=teacher.id,
            )
            db.add(session)
            db.commit()
            result = get_today_view(db, actor={'user_id': teacher.id, 'role': 'teacher'})
            self.assertEqual(len(result['today_classes']), 1)
            self.assertEqual(result['today_classes'][0]['attendance_status'], 'submitted')
        finally:
            db.close()

    def test_today_view_flags(self):
        db = self._session_factory()
        try:
            teacher = self._seed_teacher(db)
            batch = Batch(name='Batch B', subject='Science', academic_level='', active=True, start_time='10:00')
            db.add(batch)
            db.commit()
            db.refresh(batch)
            student = Student(name='Alice', guardian_phone='1', telegram_chat_id='s1', batch_id=batch.id)
            db.add(student)
            db.commit()
            db.refresh(student)
            db.add(AttendanceRecord(student_id=student.id, attendance_date=date.today(), status='Present'))
            db.add(FeeRecord(student_id=student.id, due_date=date.today(), amount=500, paid_amount=0, is_paid=False))
            db.add(StudentRiskProfile(student_id=student.id, risk_level='HIGH', final_risk_score=20))
            db.add(AttendanceRecord(student_id=student.id, attendance_date=date.today() - timedelta(days=2), status='Absent'))
            db.add(AttendanceRecord(student_id=student.id, attendance_date=date.today() - timedelta(days=1), status='Absent'))
            db.commit()
            result = get_today_view(db, actor={'user_id': teacher.id, 'role': 'teacher'})
            self.assertEqual(len(result['flags']['fee_due_present']), 1)
            self.assertEqual(len(result['flags']['high_risk_students']), 1)
            self.assertEqual(len(result['flags']['repeat_absentees']), 1)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
