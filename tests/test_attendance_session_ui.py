import tempfile
import unittest
from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import ActionToken, AttendanceRecord, Batch, BatchSchedule, ClassSession, PendingAction, Role, Student
from app.routers import attendance_session_ui
from app.services.action_token_service import create_action_token
from app.services.class_session_resolver import resolve_or_create_class_session
import app.routers.attendance_session_ui as attendance_session_ui_module


class AttendanceSessionUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_attendance_session_ui.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

        cls._orig_validate = attendance_session_ui_module.validate_session_token

        def fake_validate_session_token(token: str | None):
            if token == 'token-teacher':
                return {'user_id': 10, 'phone': '9000000000', 'role': Role.TEACHER.value}
            if token == 'token-admin':
                return {'user_id': 1, 'phone': '9000000001', 'role': Role.ADMIN.value}
            return None

        attendance_session_ui_module.validate_session_token = fake_validate_session_token

        app = FastAPI()
        app.include_router(attendance_session_ui.router)

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
        attendance_session_ui_module.validate_session_token = cls._orig_validate
        cls.client.close()
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        db = self._session_factory()
        try:
            db.query(PendingAction).delete()
            db.query(ActionToken).delete()
            db.query(AttendanceRecord).delete()
            db.query(ClassSession).delete()
            db.query(Student).delete()
            db.query(BatchSchedule).delete()
            db.query(Batch).delete()
            batch = Batch(name='Math_X', start_time='08:00', subject='Math', active=True)
            db.add(batch)
            db.commit()
            db.refresh(batch)
            db.add(BatchSchedule(batch_id=batch.id, weekday=date.today().weekday(), start_time='08:00', duration_minutes=60))
            db.add(Student(name='A', guardian_phone='9999999991', batch_id=batch.id))
            db.add(Student(name='B', guardian_phone='9999999992', batch_id=batch.id))
            db.commit()
            self.student_ids = [row.id for row in db.query(Student).order_by(Student.id.asc()).all()]
        finally:
            db.close()

    def _build_session_and_token(self):
        db = self._session_factory()
        try:
            batch = db.query(Batch).first()
            schedule = db.query(BatchSchedule).first()
            session, _ = resolve_or_create_class_session(
                db=db,
                batch_id=batch.id,
                schedule_id=schedule.id,
                target_date=date.today(),
                source='telegram',
            )
            token = create_action_token(
                db=db,
                action_type='attendance-session',
                payload={'session_id': session.id, 'teacher_id': 10},
                ttl_minutes=30,
            )['token']
            return session.id, token
        finally:
            db.close()

    def test_token_flow_submits_and_consumes(self):
        session_id, token = self._build_session_and_token()
        get_response = self.client.get(f'/ui/attendance/session/{session_id}?token={token}')
        self.assertEqual(get_response.status_code, 200)

        post_response = self.client.post(
            f'/ui/attendance/session/{session_id}',
            data={
                'token': token,
                'student_id': [str(self.student_ids[0]), str(self.student_ids[1])],
                'status': ['Present', 'Absent'],
                'comment': ['', 'Late arrival'],
            },
        )
        self.assertEqual(post_response.status_code, 200)

        post_again = self.client.post(
            f'/ui/attendance/session/{session_id}',
            data={
                'token': token,
                'student_id': [str(self.student_ids[0]), str(self.student_ids[1])],
                'status': ['Present', 'Present'],
                'comment': ['', ''],
            },
        )
        self.assertEqual(post_again.status_code, 400)

    def test_non_admin_cannot_resubmit_locked_session(self):
        session_id, token = self._build_session_and_token()
        self.client.post(
            f'/ui/attendance/session/{session_id}',
            data={
                'token': token,
                'student_id': [str(self.student_ids[0]), str(self.student_ids[1])],
                'status': ['Present', 'Absent'],
                'comment': ['', ''],
            },
        )
        teacher_retry = self.client.post(
            f'/ui/attendance/session/{session_id}',
            data={
                'student_id': [str(self.student_ids[0]), str(self.student_ids[1])],
                'status': ['Present', 'Present'],
                'comment': ['', ''],
            },
            headers={'Authorization': 'Bearer token-teacher'},
            follow_redirects=False,
        )
        self.assertEqual(teacher_retry.status_code, 303)
        self.assertIn('error=session-locked', teacher_retry.headers.get('location', ''))


if __name__ == '__main__':
    unittest.main()
