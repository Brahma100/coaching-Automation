import tempfile
import unittest
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AttendanceRecord, AuthUser, Batch, Center, Student
from app.services.first_login_service import get_activation_state


class FirstLoginServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_first_login_service.db'
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
            for table in (AttendanceRecord, Student, Batch, AuthUser, Center):
                db.query(table).delete()
            db.commit()
        finally:
            db.close()

    def _seed_center_user(self, db, *, role='admin'):
        center = Center(name='Alpha Center', slug='alpha-center', timezone='Asia/Kolkata')
        db.add(center)
        db.commit()
        db.refresh(center)
        user = AuthUser(phone='9991234567', role=role, center_id=center.id, first_login_completed=False)
        db.add(user)
        db.commit()
        db.refresh(user)
        return center, user

    def test_activation_next_action_create_batch_when_empty(self):
        db = self._session_factory()
        try:
            _, user = self._seed_center_user(db)
            state = get_activation_state(db, user)
            self.assertEqual(state['next_action'], 'create_batch')
            self.assertEqual(state['progress_percent'], 0)
            self.assertFalse(state['first_login_completed'])
        finally:
            db.close()

    def test_activation_next_action_import_students_after_batch(self):
        db = self._session_factory()
        try:
            center, user = self._seed_center_user(db)
            db.add(Batch(name='Batch A', subject='Math', academic_level='', active=True, center_id=center.id))
            db.commit()
            state = get_activation_state(db, user)
            self.assertEqual(state['next_action'], 'import_students')
            self.assertTrue(state['first_login_completed'])
        finally:
            db.close()

    def test_activation_next_action_take_attendance_after_students(self):
        db = self._session_factory()
        try:
            center, user = self._seed_center_user(db)
            batch = Batch(name='Batch B', subject='Science', academic_level='', active=True, center_id=center.id)
            db.add(batch)
            db.commit()
            db.refresh(batch)
            db.add(Student(name='Student One', guardian_phone='9999999999', batch_id=batch.id, center_id=center.id))
            db.commit()
            state = get_activation_state(db, user)
            self.assertEqual(state['next_action'], 'take_attendance')
            self.assertTrue(state['first_login_completed'])
        finally:
            db.close()

    def test_activation_dashboard_ready_when_attendance_present(self):
        db = self._session_factory()
        try:
            center, user = self._seed_center_user(db)
            batch = Batch(name='Batch C', subject='English', academic_level='', active=True, center_id=center.id)
            db.add(batch)
            db.commit()
            db.refresh(batch)
            student = Student(name='Student Two', guardian_phone='8888888888', batch_id=batch.id, center_id=center.id)
            db.add(student)
            db.commit()
            db.refresh(student)
            db.add(AttendanceRecord(student_id=student.id, attendance_date=date.today(), status='Present'))
            db.commit()
            state = get_activation_state(db, user)
            self.assertEqual(state['next_action'], 'dashboard_ready')
            self.assertEqual(state['progress_percent'], 100)
            self.assertTrue(state['first_login_completed'])
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
