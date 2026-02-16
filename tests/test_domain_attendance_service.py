import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.domain.services.attendance_service import submit_attendance as domain_submit_attendance
from app.models import AttendanceRecord, AuthUser, Batch, ClassSession, Student, TeacherBatchMap


class DomainAttendanceServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_domain_attendance_service.db'
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
            db.query(AttendanceRecord).delete()
            db.query(ClassSession).delete()
            db.query(TeacherBatchMap).delete()
            db.query(Student).delete()
            db.query(Batch).delete()
            db.query(AuthUser).delete()
            db.commit()
        finally:
            db.close()

    def test_submit_requires_actor_role(self):
        db = self._session_factory()
        try:
            batch = Batch(id=101, name='Batch A', subject='Math', active=True, start_time='09:00', center_id=1)
            student = Student(id=201, name='S1', guardian_phone='9000000001', batch_id=101, center_id=1)
            db.add_all([batch, student])
            db.commit()

            with self.assertRaises(ValueError):
                domain_submit_attendance(
                    db=db,
                    batch_id=101,
                    attendance_date=datetime.utcnow().date(),
                    records=[{'student_id': 201, 'status': 'Present', 'comment': ''}],
                    actor_role=None,
                    actor_user_id=0,
                )
        finally:
            db.close()

    def test_teacher_cannot_submit_outside_scope(self):
        db = self._session_factory()
        try:
            teacher = AuthUser(phone='9000000099', role='teacher', center_id=1)
            batch_owned = Batch(id=111, name='Owned Batch', subject='Math', active=True, start_time='09:00', center_id=1)
            batch_other = Batch(id=112, name='Other Batch', subject='Science', active=True, start_time='10:00', center_id=1)
            student_other = Student(id=212, name='S2', guardian_phone='9000000002', batch_id=112, center_id=1)
            db.add_all([teacher, batch_owned, batch_other, student_other])
            db.commit()
            db.refresh(teacher)
            session_other = ClassSession(
                id=312,
                batch_id=112,
                subject='Science',
                scheduled_start=datetime.utcnow(),
                duration_minutes=60,
                teacher_id=teacher.id,
                center_id=1,
                status='open',
            )

            db.add(TeacherBatchMap(teacher_id=teacher.id, batch_id=batch_owned.id, center_id=1, is_primary=True))
            db.add(session_other)
            db.commit()

            with self.assertRaises(PermissionError):
                domain_submit_attendance(
                    db=db,
                    session_id=312,
                    batch_id=112,
                    attendance_date=session_other.scheduled_start.date(),
                    records=[{'student_id': 212, 'status': 'Present', 'comment': ''}],
                    actor_role='teacher',
                    actor_user_id=teacher.id,
                    teacher_id=teacher.id,
                )
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
