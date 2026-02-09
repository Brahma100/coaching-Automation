import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import AttendanceRecord, FeeRecord, Homework, HomeworkSubmission, Role, Student
from app.routers import student_api
from app.services import student_portal_service


class StudentPortalApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_student_portal.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

        cls._orig_validate = student_portal_service.validate_session_token

        def fake_validate_session_token(token: str | None):
            if token == 'token-student-1':
                return {'sub': 1, 'phone': '9000000001', 'role': Role.STUDENT.value}
            if token == 'token-teacher':
                return {'sub': 2, 'phone': '9000000099', 'role': Role.TEACHER.value}
            return None

        student_portal_service.validate_session_token = fake_validate_session_token

        app = FastAPI()
        app.include_router(student_api.router)

        def override_get_db():
            db = cls._session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        student_portal_service.validate_session_token = cls._orig_validate
        cls.client.close()
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        db = self._session_factory()
        try:
            db.query(HomeworkSubmission).delete()
            db.query(Homework).delete()
            db.query(AttendanceRecord).delete()
            db.query(FeeRecord).delete()
            db.query(Student).delete()

            s1 = Student(name='Student One', guardian_phone='9000000001', batch_id=1)
            s2 = Student(name='Student Two', guardian_phone='9000000002', batch_id=1)
            db.add_all([s1, s2])
            db.commit()
            db.refresh(s1)
            db.refresh(s2)

            db.add_all(
                [
                    AttendanceRecord(student_id=s1.id, attendance_date=date.today(), status='Present', comment=''),
                    AttendanceRecord(student_id=s2.id, attendance_date=date.today(), status='Absent', comment=''),
                ]
            )
            db.add_all(
                [
                    FeeRecord(student_id=s1.id, due_date=date.today() + timedelta(days=10), amount=1000, paid_amount=0, is_paid=False),
                    FeeRecord(student_id=s2.id, due_date=date.today() - timedelta(days=5), amount=1000, paid_amount=0, is_paid=False),
                ]
            )
            hw1 = Homework(title='HW 1', description='', due_date=date.today() + timedelta(days=3), created_at=datetime.utcnow())
            hw2 = Homework(title='HW 2', description='', due_date=date.today() + timedelta(days=4), created_at=datetime.utcnow())
            db.add_all([hw1, hw2])
            db.commit()
            db.refresh(hw1)
            db.refresh(hw2)
            db.add(HomeworkSubmission(homework_id=hw1.id, student_id=s1.id, file_path=''))
            db.commit()
        finally:
            db.close()

    def test_student_can_access_own_data(self):
        me = self.client.get('/api/student/me', headers={'Authorization': 'Bearer token-student-1'})
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()['student']['name'], 'Student One')

        attendance = self.client.get('/api/student/attendance', headers={'Authorization': 'Bearer token-student-1'})
        self.assertEqual(attendance.status_code, 200)
        self.assertEqual(len(attendance.json()), 1)
        self.assertEqual(attendance.json()[0]['status'], 'Present')

        fees = self.client.get('/api/student/fees', headers={'Authorization': 'Bearer token-student-1'})
        self.assertEqual(fees.status_code, 200)
        self.assertEqual(len(fees.json()), 1)
        self.assertEqual(fees.json()[0]['status'], 'Due')

    def test_non_student_cannot_access(self):
        response = self.client.get('/api/student/me', headers={'Authorization': 'Bearer token-teacher'})
        self.assertEqual(response.status_code, 403)

    def test_homework_is_read_only_and_scoped(self):
        response = self.client.get('/api/student/homework', headers={'Authorization': 'Bearer token-student-1'})
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertEqual(len(rows), 2)
        statuses = {row['title']: row['submission_status'] for row in rows}
        self.assertEqual(statuses['HW 1'], 'Submitted')
        self.assertEqual(statuses['HW 2'], 'Pending')


if __name__ == '__main__':
    unittest.main()
