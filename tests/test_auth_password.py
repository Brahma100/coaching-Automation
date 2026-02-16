import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import AllowedUser, AllowedUserStatus, AuthUser, Role
from app.routers import auth


class AuthPasswordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_auth_password.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

        app = FastAPI()
        app.include_router(auth.router)

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
        cls.client.close()
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        db = self._session_factory()
        try:
            db.query(AllowedUser).delete()
            db.add_all(
                [
                    AllowedUser(phone='9000000001', role=Role.TEACHER.value, status=AllowedUserStatus.ACTIVE.value),
                    AllowedUser(phone='9000000002', role=Role.TEACHER.value, status=AllowedUserStatus.DISABLED.value),
                ]
            )
            db.commit()
        finally:
            db.close()

    def test_signup_and_login_password(self):
        signup = self.client.post('/auth/signup-password', json={'phone': '9000000001', 'password': 'Password@123'})
        self.assertEqual(signup.status_code, 200)
        self.assertTrue(signup.json().get('ok'))
        self.assertIn('auth_session', signup.cookies)

        login = self.client.post('/auth/login-password', json={'phone': '9000000001', 'password': 'Password@123'})
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json().get('ok'))

    def test_login_password_accepts_country_code_variant(self):
        signup = self.client.post('/auth/signup-password', json={'phone': '9000000001', 'password': 'Password@123'})
        self.assertEqual(signup.status_code, 200)

        login = self.client.post('/auth/login-password', json={'phone': '+919000000001', 'password': 'Password@123'})
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json().get('ok'))

    def test_disabled_allowlist_denied(self):
        signup = self.client.post('/auth/signup-password', json={'phone': '9000000002', 'password': 'Password@123'})
        self.assertEqual(signup.status_code, 403)

    def test_google_not_configured(self):
        response = self.client.post('/auth/google-login', json={'id_token': 'dummy'})
        self.assertEqual(response.status_code, 501)

    def test_request_otp_uses_gateway_delivery(self):
        db = self._session_factory()
        try:
            user = db.query(AuthUser).filter(AuthUser.phone == '9000000001').first()
            if not user:
                user = AuthUser(phone='9000000001', role=Role.TEACHER.value)
                db.add(user)
            user.telegram_chat_id = 'chat-otp-1'
            db.commit()
        finally:
            db.close()

        with patch('app.services.auth_service.gateway_send_event', return_value=[{'ok': True, 'status': 'sent'}]) as gateway_send:
            response = self.client.post('/auth/request-otp', json={'phone': '9000000001'})

        self.assertEqual(response.status_code, 200)
        gateway_send.assert_called_once()


if __name__ == '__main__':
    unittest.main()
