import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import AuthUser, Batch, ClassSession, Student, TeacherBatchMap
from app.routers import actions
import app.routers.actions as actions_module


class ActionsTokenCreateSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_actions_token_create_security.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

        cls._orig_validate = actions_module.validate_session_token

        def fake_validate_session_token(token: str | None):
            if token == 'token-teacher':
                return {'user_id': 10, 'role': 'teacher', 'center_id': 1}
            if token == 'token-admin':
                return {'user_id': 1, 'role': 'admin', 'center_id': 1}
            return None

        actions_module.validate_session_token = fake_validate_session_token

        app = FastAPI()
        app.include_router(actions.router)

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
        actions_module.validate_session_token = cls._orig_validate
        cls.client.close()
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        db = self._session_factory()
        try:
            db.query(TeacherBatchMap).delete()
            db.query(ClassSession).delete()
            db.query(Student).delete()
            db.query(Batch).delete()
            db.query(AuthUser).delete()

            admin = AuthUser(id=1, phone='9000000001', role='admin', center_id=1)
            teacher = AuthUser(id=10, phone='9000000010', role='teacher', center_id=1)
            batch_1 = Batch(id=101, name='Batch 1', subject='Math', active=True, start_time='09:00', center_id=1)
            batch_2 = Batch(id=102, name='Batch 2', subject='Science', active=True, start_time='10:00', center_id=1)
            batch_other_center = Batch(id=201, name='Batch X', subject='Physics', active=True, start_time='11:00', center_id=2)
            student = Student(id=301, name='S1', guardian_phone='9000000301', batch_id=101, center_id=1)
            session_owned = ClassSession(
                id=401,
                batch_id=101,
                subject='Math',
                scheduled_start=datetime.utcnow(),
                duration_minutes=60,
                teacher_id=10,
                center_id=1,
                status='open',
            )
            session_unscoped = ClassSession(
                id=402,
                batch_id=102,
                subject='Science',
                scheduled_start=datetime.utcnow(),
                duration_minutes=60,
                teacher_id=99,
                center_id=1,
                status='open',
            )
            db.add_all([admin, teacher, batch_1, batch_2, batch_other_center, student, session_owned, session_unscoped])
            db.add(TeacherBatchMap(teacher_id=10, batch_id=101, center_id=1, is_primary=True))
            db.commit()
        finally:
            db.close()

    def test_unauthenticated_request_rejected(self):
        response = self.client.post(
            '/actions/token/create',
            json={'action_type': 'session_summary', 'payload': {'center_id': 1, 'expected_role': 'teacher', 'session_id': 401}},
        )
        self.assertEqual(response.status_code, 401)

    def test_cross_center_token_request_rejected(self):
        response = self.client.post(
            '/actions/token/create',
            headers={'Authorization': 'Bearer token-admin'},
            json={'action_type': 'session_summary', 'payload': {'center_id': 2, 'expected_role': 'teacher', 'batch_id': 201}},
        )
        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_mint_for_unscoped_session(self):
        response = self.client.post(
            '/actions/token/create',
            headers={'Authorization': 'Bearer token-teacher'},
            json={'action_type': 'session_summary', 'payload': {'center_id': 1, 'expected_role': 'teacher', 'session_id': 402}},
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_mint_within_center(self):
        response = self.client.post(
            '/actions/token/create',
            headers={'Authorization': 'Bearer token-admin'},
            json={'action_type': 'session_summary', 'payload': {'center_id': 1, 'expected_role': 'teacher', 'session_id': 401}},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn('token', body)
        self.assertEqual(body.get('action_type'), 'session_summary')


if __name__ == '__main__':
    unittest.main()
