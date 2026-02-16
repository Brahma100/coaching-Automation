import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AllowedUser, AuthUser, Center, OnboardingState
from app.services.auth_service import _encode_jwt, validate_session_token
from app.services.onboarding_service import (
    check_slug_availability,
    create_admin_user,
    create_center_setup,
    get_onboarding_state,
    is_center_onboarding_incomplete,
    parse_students_csv,
    reserve_slug,
)


class OnboardingFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_onboarding_flow.db'
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
            db.query(OnboardingState).delete()
            db.query(AllowedUser).delete()
            db.query(AuthUser).delete()
            db.query(Center).delete()
            db.commit()
        finally:
            db.close()

    def _token(self, *, user_id: int, phone: str, role: str, center_id: int) -> str:
        return _encode_jwt(
            {
                'sub': int(user_id),
                'phone': phone,
                'role': role,
                'center_id': int(center_id),
                'iat': 0,
            }
        )

    def test_onboarding_creates_isolated_center_and_slug_collision_prevented(self):
        db = self._session_factory()
        try:
            row_a, _ = create_center_setup(
                db,
                name='Alpha Institute',
                city='Pune',
                timezone='Asia/Kolkata',
                academic_type='school',
            )
            row_b, _ = create_center_setup(
                db,
                name='Beta Institute',
                city='Delhi',
                timezone='Asia/Kolkata',
                academic_type='jee',
            )
            self.assertNotEqual(int(row_a.center_id), int(row_b.center_id))

            available, _ = check_slug_availability(db, row_a.temp_slug)
            self.assertFalse(available)
        finally:
            db.close()

    def test_admin_linked_correctly_and_resume_works(self):
        db = self._session_factory()
        try:
            row, _ = create_center_setup(
                db,
                name='Gamma Academy',
                city='Mumbai',
                timezone='Asia/Kolkata',
                academic_type='school',
            )
            row = reserve_slug(db, setup_token=row.setup_token, slug='gamma-academy')
            resumed = get_onboarding_state(db, row.setup_token)
            self.assertEqual(resumed.current_step, 'subdomain_selection')

            row, session_token = create_admin_user(
                db,
                setup_token=row.setup_token,
                name='Owner',
                phone='9999911111',
                password='securepass123',
            )
            self.assertTrue(session_token)
            admin = db.query(AuthUser).filter(AuthUser.phone == '9999911111').first()
            self.assertIsNotNone(admin)
            self.assertEqual(int(admin.center_id), int(row.center_id))
            self.assertEqual(str(admin.role), 'admin')
        finally:
            db.close()

    def test_cross_center_onboarding_access_rejected(self):
        db = self._session_factory()
        try:
            row_a, _ = create_center_setup(
                db,
                name='A Center',
                city='A',
                timezone='Asia/Kolkata',
                academic_type='school',
            )
            row_b, _ = create_center_setup(
                db,
                name='B Center',
                city='B',
                timezone='Asia/Kolkata',
                academic_type='school',
            )
            with self.assertRaises(ValueError):
                _ = get_onboarding_state(db, row_a.setup_token, actor_center_id=int(row_b.center_id))
        finally:
            db.close()

    def test_unfinished_onboarding_cannot_access_dashboard(self):
        db = self._session_factory()
        try:
            row, _ = create_center_setup(
                db,
                name='Delta Coaching',
                city='Noida',
                timezone='Asia/Kolkata',
                academic_type='school',
            )
            user = AuthUser(phone='9999922222', role='admin', center_id=row.center_id)
            db.add(user)
            db.commit()
            db.refresh(user)
            token = self._token(user_id=int(user.id), phone=user.phone, role='admin', center_id=int(row.center_id))
        finally:
            db.close()

        app = FastAPI()

        @app.middleware('http')
        async def onboarding_guard(request: Request, call_next):
            if request.url.path.startswith('/api/dashboard'):
                auth_header = request.headers.get('Authorization', '')
                bearer = auth_header.split(' ', 1)[1].strip() if auth_header.lower().startswith('bearer ') else ''
                session = validate_session_token(bearer)
                center_id = int((session or {}).get('center_id') or 0)
                if center_id > 0:
                    db_guard = self._session_factory()
                    try:
                        if is_center_onboarding_incomplete(db_guard, center_id):
                            return JSONResponse(status_code=403, content={'detail': 'Onboarding incomplete'})
                    finally:
                        db_guard.close()
            return await call_next(request)

        @app.get('/api/dashboard/probe')
        def dashboard_probe():
            return {'ok': True}

        client = TestClient(app)
        response = client.get('/api/dashboard/probe', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json().get('detail'), 'Onboarding incomplete')

    def test_students_csv_validation_report(self):
        csv_bytes = (
            "name,guardian_phone,batch\n"
            "Student One,9876543210,A1\n"
            "Student Two,123,A2\n"
            ",9999999999,A3\n"
        ).encode('utf-8')
        report = parse_students_csv(csv_bytes)
        self.assertEqual(report.get('missing_headers'), [])
        self.assertEqual(len(report.get('rows') or []), 1)
        self.assertEqual(len(report.get('row_errors') or []), 2)


if __name__ == '__main__':
    unittest.main()
