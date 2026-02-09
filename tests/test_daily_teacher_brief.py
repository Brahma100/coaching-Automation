import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import AttendanceRecord, ClassSession, FeeRecord, Homework, PendingAction, Student, StudentRiskProfile
from app.routers import teacher_brief
from app.services.daily_teacher_brief_service import build_daily_teacher_brief, format_daily_teacher_brief


class DailyTeacherBriefTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_teacher_brief.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

        cls._orig_validate = teacher_brief.validate_session_token

        def fake_validate(token: str | None):
            if token == 'token-teacher':
                return {'user_id': 10, 'phone': '9000000001', 'role': 'teacher'}
            return None

        teacher_brief.validate_session_token = fake_validate

        app = FastAPI()
        app.include_router(teacher_brief.router)

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
        teacher_brief.validate_session_token = cls._orig_validate
        cls.client.close()
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        db = self._session_factory()
        try:
            db.query(PendingAction).delete()
            db.query(StudentRiskProfile).delete()
            db.query(AttendanceRecord).delete()
            db.query(FeeRecord).delete()
            db.query(Student).delete()
            db.query(ClassSession).delete()
            db.query(Homework).delete()

            student = Student(name='Alice', guardian_phone='9000000011', batch_id=7)
            db.add(student)
            db.commit()
            db.refresh(student)

            session = ClassSession(
                batch_id=7,
                subject='Math',
                scheduled_start=datetime.now() + timedelta(hours=1),
                topic_planned='Algebra',
                teacher_id=10,
                status='scheduled',
            )
            db.add(session)
            db.commit()
            db.refresh(session)

            db.add(AttendanceRecord(student_id=student.id, attendance_date=date.today(), status='Absent', comment='Sick'))
            db.add(FeeRecord(student_id=student.id, due_date=date.today(), amount=1200, paid_amount=0, is_paid=False))
            db.add(
                Homework(
                    title='Worksheet 1',
                    description='',
                    due_date=date.today() + timedelta(days=1),
                    created_at=datetime.utcnow(),
                )
            )
            db.add(
                PendingAction(
                    type='absence',
                    student_id=student.id,
                    related_session_id=session.id,
                    status='open',
                    note='Follow up with parent',
                )
            )
            db.add(
                StudentRiskProfile(
                    student_id=student.id,
                    attendance_score=0.3,
                    homework_score=0.4,
                    fee_score=0.5,
                    final_risk_score=40.0,
                    risk_level='HIGH',
                )
            )
            db.commit()
        finally:
            db.close()

    def test_service_builds_expected_sections(self):
        db = self._session_factory()
        try:
            summary = build_daily_teacher_brief(db, teacher_id=10, day=date.today())
        finally:
            db.close()

        self.assertEqual(summary['class_schedule']['count'], 1)
        self.assertEqual(summary['absent_students']['count'], 1)
        self.assertEqual(summary['pending_actions']['count'], 1)
        self.assertEqual(summary['fee_due']['count'], 1)
        self.assertEqual(summary['homework_due']['count'], 1)
        self.assertEqual(summary['high_risk_students']['count'], 1)

        text = format_daily_teacher_brief(summary, teacher_phone='9000000001')
        self.assertIn('Daily Teacher Brief', text)
        self.assertIn('Class Schedule:', text)
        self.assertIn('HIGH risk:', text)

    def test_api_returns_today_summary(self):
        response = self.client.get('/api/teacher/brief/today', headers={'Authorization': 'Bearer token-teacher'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('class_schedule', payload)
        self.assertIn('absent_students', payload)


if __name__ == '__main__':
    unittest.main()
