import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.services.action_token_service import create_action_token, load_token_row
from app.routers import tokens


class TokenValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_tokens.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

        app = FastAPI()
        app.include_router(tokens.router)

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

    def test_validate_token_ok(self):
        db = self._session_factory()
        try:
            token = create_action_token(
                db,
                action_type='attendance_open',
                payload={'session_id': 123, 'role': 'teacher'},
                ttl_minutes=60,
            )['token']
        finally:
            db.close()

        resp = self.client.get('/api/tokens/validate', params={'token': token, 'session_id': 123, 'expected': 'attendance_open'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['valid'])

    def test_validate_token_expired_marks_consumed(self):
        db = self._session_factory()
        try:
            token = create_action_token(
                db,
                action_type='attendance_open',
                payload={'session_id': 200},
                ttl_minutes=1,
            )['token']
            row = load_token_row(db, token)
            row.expires_at = datetime.utcnow() - timedelta(minutes=1)
            db.commit()
        finally:
            db.close()

        resp = self.client.get('/api/tokens/validate', params={'token': token, 'session_id': 200, 'expected': 'attendance_open'})
        self.assertEqual(resp.status_code, 401)

        db = self._session_factory()
        try:
            row = load_token_row(db, token)
            self.assertTrue(row.consumed)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
