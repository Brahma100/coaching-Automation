import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import (
    ActionToken,
    AdminOpsSnapshot,
    AttendanceRecord,
    AuthUser,
    Batch,
    BatchSchedule,
    ClassSession,
    FeeRecord,
    Parent,
    ParentStudentMap,
    PendingAction,
    Student,
    StudentDashboardSnapshot,
    TeacherBatchMap,
    TeacherTodaySnapshot,
)
from app.services.dashboard_today_service import clear_today_view_cache, get_today_view
from app.services.student_portal_service import resolve_student_for_session


class RoleBasedScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_role_scope.db'
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
                TeacherBatchMap,
                StudentDashboardSnapshot,
                TeacherTodaySnapshot,
                AdminOpsSnapshot,
                ParentStudentMap,
                Parent,
                Student,
                Batch,
                AuthUser,
            ):
                db.query(table).delete()
            db.commit()
        finally:
            db.close()

    def test_teacher_cannot_see_other_teacher_batches(self):
        db = self._session_factory()
        try:
            teacher_a = AuthUser(phone='9990001001', role='teacher')
            teacher_b = AuthUser(phone='9990001002', role='teacher')
            db.add_all([teacher_a, teacher_b])
            db.commit()
            db.refresh(teacher_a)
            db.refresh(teacher_b)

            batch_a = Batch(name='Scope Batch A', subject='Math', academic_level='', active=True, start_time='09:00')
            batch_b = Batch(name='Scope Batch B', subject='Science', academic_level='', active=True, start_time='11:00')
            db.add_all([batch_a, batch_b])
            db.commit()
            db.refresh(batch_a)
            db.refresh(batch_b)

            db.add_all(
                [
                    TeacherBatchMap(teacher_id=teacher_a.id, batch_id=batch_a.id, is_primary=True),
                    TeacherBatchMap(teacher_id=teacher_b.id, batch_id=batch_b.id, is_primary=True),
                    BatchSchedule(batch_id=batch_a.id, weekday=date.today().weekday(), start_time='09:00', duration_minutes=60),
                    BatchSchedule(batch_id=batch_b.id, weekday=date.today().weekday(), start_time='11:00', duration_minutes=60),
                ]
            )
            db.commit()

            db.add_all(
                [
                    ClassSession(
                        batch_id=batch_a.id,
                        subject='Math',
                        scheduled_start=datetime.combine(date.today(), datetime.strptime('09:00', '%H:%M').time()),
                        duration_minutes=60,
                        status='scheduled',
                        teacher_id=teacher_a.id,
                    ),
                    ClassSession(
                        batch_id=batch_b.id,
                        subject='Science',
                        scheduled_start=datetime.combine(date.today(), datetime.strptime('11:00', '%H:%M').time()),
                        duration_minutes=60,
                        status='scheduled',
                        teacher_id=teacher_b.id,
                    ),
                ]
            )
            db.commit()

            payload = get_today_view(db, actor={'user_id': teacher_a.id, 'role': 'teacher'})
            visible_batch_ids = {int(row['batch_id']) for row in payload.get('today_classes', [])}
            self.assertIn(batch_a.id, visible_batch_ids)
            self.assertNotIn(batch_b.id, visible_batch_ids)
        finally:
            db.close()

    def test_student_cannot_access_other_student_data(self):
        db = self._session_factory()
        try:
            batch = Batch(name='Student Scope Batch', subject='Math', academic_level='', active=True, start_time='08:00')
            db.add(batch)
            db.commit()
            db.refresh(batch)

            student_a = Student(name='Student A', guardian_phone='9000000001', telegram_chat_id='a1', batch_id=batch.id)
            student_b = Student(name='Student B', guardian_phone='9000000002', telegram_chat_id='b1', batch_id=batch.id)
            db.add_all([student_a, student_b])
            db.commit()
            db.refresh(student_a)
            db.refresh(student_b)

            resolved = resolve_student_for_session(db, {'role': 'student', 'phone': '9000000001'})
            self.assertEqual(resolved.id, student_a.id)
            self.assertNotEqual(resolved.id, student_b.id)
        finally:
            db.close()

    def test_admin_unrestricted(self):
        db = self._session_factory()
        try:
            admin = AuthUser(phone='9990002000', role='admin')
            teacher = AuthUser(phone='9990002001', role='teacher')
            db.add_all([admin, teacher])
            db.commit()
            db.refresh(admin)
            db.refresh(teacher)

            batch_a = Batch(name='Admin Batch A', subject='Math', academic_level='', active=True, start_time='09:00')
            batch_b = Batch(name='Admin Batch B', subject='Science', academic_level='', active=True, start_time='12:00')
            db.add_all([batch_a, batch_b])
            db.commit()
            db.refresh(batch_a)
            db.refresh(batch_b)

            db.add_all(
                [
                    TeacherBatchMap(teacher_id=teacher.id, batch_id=batch_a.id, is_primary=True),
                    BatchSchedule(batch_id=batch_a.id, weekday=date.today().weekday(), start_time='09:00', duration_minutes=60),
                    BatchSchedule(batch_id=batch_b.id, weekday=date.today().weekday(), start_time='12:00', duration_minutes=60),
                    ClassSession(
                        batch_id=batch_a.id,
                        subject='Math',
                        scheduled_start=datetime.combine(date.today(), datetime.strptime('09:00', '%H:%M').time()),
                        duration_minutes=60,
                        status='scheduled',
                        teacher_id=teacher.id,
                    ),
                    ClassSession(
                        batch_id=batch_b.id,
                        subject='Science',
                        scheduled_start=datetime.combine(date.today(), datetime.strptime('12:00', '%H:%M').time()),
                        duration_minutes=60,
                        status='scheduled',
                        teacher_id=teacher.id,
                    ),
                ]
            )
            db.commit()

            payload = get_today_view(db, actor={'user_id': admin.id, 'role': 'admin'})
            visible_batch_ids = {int(row['batch_id']) for row in payload.get('today_classes', [])}
            self.assertIn(batch_a.id, visible_batch_ids)
            self.assertIn(batch_b.id, visible_batch_ids)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
