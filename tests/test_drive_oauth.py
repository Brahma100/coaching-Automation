import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import DriveOAuthToken
from app.routers import drive_oauth
from app.services import drive_oauth_service


class DriveOAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_drive_oauth.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

        cls._orig_validate_session_token = drive_oauth.validate_session_token
        cls._orig_exchange_code = drive_oauth.exchange_code_for_refresh_token

        def fake_validate_session_token(token: str | None):
            if token == 'token-admin':
                return {'user_id': 9001, 'phone': '9999999999', 'role': 'admin'}
            return None

        drive_oauth.validate_session_token = fake_validate_session_token

        app = FastAPI()
        app.include_router(drive_oauth.router)

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
        drive_oauth.validate_session_token = cls._orig_validate_session_token
        drive_oauth.exchange_code_for_refresh_token = cls._orig_exchange_code
        cls.client.close()
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        db = self._session_factory()
        try:
            db.query(DriveOAuthToken).delete()
            db.commit()
        finally:
            db.close()

    def test_oauth_callback_stores_refresh_token(self):
        def fake_exchange(code: str):
            return 'refresh-token-xyz', 'access-token-abc'

        drive_oauth.exchange_code_for_refresh_token = fake_exchange

        response = self.client.get('/api/drive/oauth/callback?code=test-code', headers={'Authorization': 'Bearer token-admin'})
        self.assertEqual(response.status_code, 200)

        db = self._session_factory()
        try:
            row = db.query(DriveOAuthToken).filter(DriveOAuthToken.user_id == 9001).first()
            self.assertIsNotNone(row)
            self.assertNotEqual(row.refresh_token, 'refresh-token-xyz')
        finally:
            db.close()

    def test_drive_status_endpoint(self):
        response = self.client.get('/api/drive/status', headers={'Authorization': 'Bearer token-admin'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'connected': False})

    def test_token_refresh_flow_mocked(self):
        db = self._session_factory()
        try:
            drive_oauth_service.store_refresh_token(db, user_id=9001, refresh_token='refresh-token-123')
        finally:
            db.close()

        original_credentials = drive_oauth_service.Credentials

        class FakeCredentials:
            def __init__(self, token=None, refresh_token=None, token_uri=None, client_id=None, client_secret=None, scopes=None):
                self.token = token
                self.refresh_token = refresh_token
                self.token_uri = token_uri
                self.client_id = client_id
                self.client_secret = client_secret
                self.scopes = scopes

            def refresh(self, request_obj):
                _ = request_obj
                self.token = 'fresh-access-token'

        drive_oauth_service.Credentials = FakeCredentials
        try:
            db = self._session_factory()
            try:
                creds = drive_oauth_service.get_drive_credentials(db, user_id=9001)
                self.assertEqual(creds.token, 'fresh-access-token')
                self.assertEqual(creds.refresh_token, 'refresh-token-123')
            finally:
                db.close()
        finally:
            drive_oauth_service.Credentials = original_credentials


if __name__ == '__main__':
    unittest.main()
