import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.services.action_token_service import consume_token, create_action_token, load_token_row, verify_token
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

    def test_validate_token_expired_does_not_consume(self):
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
            self.assertFalse(row.consumed)
        finally:
            db.close()

    def test_verify_token_rejects_wrong_role(self):
        db = self._session_factory()
        try:
            token = create_action_token(
                db,
                action_type='attendance_open',
                payload={'session_id': 301},
                ttl_minutes=60,
                expected_role='teacher',
                center_id=1,
            )['token']
            with self.assertRaises(ValueError):
                verify_token(
                    db,
                    token,
                    expected_action_type='attendance_open',
                    request_role='student',
                    request_center_id=1,
                )
        finally:
            db.close()

    def test_verify_token_rejects_cross_center(self):
        db = self._session_factory()
        try:
            token = create_action_token(
                db,
                action_type='attendance_open',
                payload={'session_id': 302},
                ttl_minutes=60,
                expected_role='teacher',
                center_id=1,
            )['token']
            with self.assertRaises(ValueError):
                verify_token(
                    db,
                    token,
                    expected_action_type='attendance_open',
                    request_role='teacher',
                    request_center_id=2,
                )
        finally:
            db.close()

    def test_consume_token_rejects_double_use(self):
        db = self._session_factory()
        try:
            token = create_action_token(
                db,
                action_type='attendance_open',
                payload={'session_id': 303},
                ttl_minutes=60,
            )['token']
            payload = verify_token(db, token, expected_action_type='attendance_open')
            self.assertEqual(int(payload.get('session_id') or 0), 303)
            consume_token(db, token)
            with self.assertRaises(ValueError):
                consume_token(db, token)
        finally:
            db.close()

    def test_load_token_uses_constant_time_hash_compare(self):
        db = self._session_factory()
        try:
            token = create_action_token(
                db,
                action_type='attendance_open',
                payload={'session_id': 304},
                ttl_minutes=60,
            )['token']
            with patch('app.services.action_token_service.hmac.compare_digest', wraps=__import__('hmac').compare_digest) as mocked_compare:
                row = load_token_row(db, token)
                self.assertIsNotNone(row)
                self.assertGreaterEqual(mocked_compare.call_count, 1)
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
