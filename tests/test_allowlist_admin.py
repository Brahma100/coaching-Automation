import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import AllowedUser, AllowedUserStatus, Role
from app.routers import allowlist_admin
from app.services import allowlist_admin_service


class AllowlistAdminApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_allowlist_admin.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

        cls._orig_validate = allowlist_admin_service.validate_session_token

        def fake_validate_session_token(token: str | None):
            if token == 'token-admin':
                return {'sub': 1, 'phone': '1111111111', 'role': 'admin'}
            if token == 'token-teacher':
                return {'sub': 2, 'phone': '2222222222', 'role': 'teacher'}
            return None

        allowlist_admin_service.validate_session_token = fake_validate_session_token

        app = FastAPI()
        app.include_router(allowlist_admin.router)

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
        allowlist_admin_service.validate_session_token = cls._orig_validate
        cls.client.close()
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        db = self._session_factory()
        try:
            db.query(AllowedUser).delete()
            db.add_all(
                [
                    AllowedUser(phone='1111111111', role=Role.ADMIN.value, status=AllowedUserStatus.ACTIVE.value),
                    AllowedUser(phone='2222222222', role=Role.TEACHER.value, status=AllowedUserStatus.ACTIVE.value),
                ]
            )
            db.commit()
        finally:
            db.close()

    def test_admin_can_list_users(self):
        response = self.client.get('/api/admin/allowed-users', headers={'Authorization': 'Bearer token-admin'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertIn('phone', data[0])

    def test_admin_can_invite(self):
        payload = {'phone': '3333333333', 'role': 'TEACHER'}
        response = self.client.post(
            '/api/admin/allowed-users/invite',
            json=payload,
            headers={'Authorization': 'Bearer token-admin'},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['phone'], '3333333333')
        self.assertEqual(data['role'], 'teacher')
        self.assertEqual(data['status'], 'invited')

    def test_non_admin_cannot_access(self):
        response = self.client.get('/api/admin/allowed-users', headers={'Authorization': 'Bearer token-teacher'})
        self.assertEqual(response.status_code, 403)

    def test_activate_and_deactivate(self):
        invite = self.client.post(
            '/api/admin/allowed-users/invite',
            json={'phone': '4444444444', 'role': 'STUDENT'},
            headers={'Authorization': 'Bearer token-admin'},
        )
        self.assertEqual(invite.status_code, 200)
        self.assertEqual(invite.json()['status'], 'invited')

        activate = self.client.post(
            '/api/admin/allowed-users/activate',
            json={'phone': '4444444444'},
            headers={'Authorization': 'Bearer token-admin'},
        )
        self.assertEqual(activate.status_code, 200)
        self.assertEqual(activate.json()['status'], 'active')

        deactivate = self.client.post(
            '/api/admin/allowed-users/deactivate',
            json={'phone': '4444444444'},
            headers={'Authorization': 'Bearer token-admin'},
        )
        self.assertEqual(deactivate.status_code, 200)
        self.assertEqual(deactivate.json()['status'], 'disabled')


if __name__ == '__main__':
    unittest.main()
