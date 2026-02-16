import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.cache import cache, cache_key
from app.db import Base
from app.models import AuthUser, Center
from app.services.auth_service import _encode_jwt
from app.tenant_middleware import TenantResolutionMiddleware, get_request_center_id


class TenantMiddlewareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_tenant_middleware.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

        app = FastAPI()
        app.add_middleware(TenantResolutionMiddleware, session_factory=cls._session_factory)

        @app.get('/private')
        def private_route(request: Request):
            return {'ok': True, 'center_id': get_request_center_id(request)}

        @app.get('/cached')
        def cached_route(request: Request):
            key = cache_key('tenant_probe', 'fixed')
            cached = cache.get_cached(key)
            if cached is None:
                cached = {'center_id': get_request_center_id(request)}
                cache.set_cached(key, cached, ttl=60)
            return cached

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        db = self._session_factory()
        try:
            cache.invalidate_prefix('tenant_probe')
            db.query(AuthUser).delete()
            db.query(Center).delete()
            db.commit()

            default_center = Center(name='Default', slug='default-center', timezone='Asia/Kolkata')
            alpha = Center(name='Alpha', slug='alpha', timezone='Asia/Kolkata')
            beta = Center(name='Beta', slug='beta', timezone='Asia/Kolkata')
            db.add_all([default_center, alpha, beta])
            db.commit()
            db.refresh(default_center)
            db.refresh(alpha)
            db.refresh(beta)
            self.default_center_id = int(default_center.id)
            self.alpha_id = int(alpha.id)
            self.beta_id = int(beta.id)

            db.add_all(
                [
                    AuthUser(phone='9000000001', role='teacher', center_id=self.alpha_id),
                    AuthUser(phone='9000000002', role='teacher', center_id=self.beta_id),
                ]
            )
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

    def test_cross_center_access_blocked(self):
        token_alpha = self._token(user_id=1, phone='9000000001', role='teacher', center_id=self.alpha_id)
        response = self.client.get(
            '/private',
            headers={'host': 'beta.yourapp.com'},
            cookies={'auth_session': token_alpha},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json().get('detail'), 'Center mismatch')

    def test_wrong_subdomain_login_denied(self):
        token_beta = self._token(user_id=2, phone='9000000002', role='teacher', center_id=self.beta_id)
        response = self.client.get(
            '/private',
            headers={
                'host': 'alpha.yourapp.com',
                'authorization': f'Bearer {token_beta}',
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json().get('detail'), 'Center mismatch')

    def test_cache_isolation_verified(self):
        response_alpha_1 = self.client.get('/cached', headers={'host': 'alpha.yourapp.com'})
        response_alpha_2 = self.client.get('/cached', headers={'host': 'alpha.yourapp.com'})
        response_beta_1 = self.client.get('/cached', headers={'host': 'beta.yourapp.com'})

        self.assertEqual(response_alpha_1.status_code, 200)
        self.assertEqual(response_alpha_2.status_code, 200)
        self.assertEqual(response_beta_1.status_code, 200)
        self.assertEqual(int(response_alpha_1.json().get('center_id') or 0), self.alpha_id)
        self.assertEqual(int(response_alpha_2.json().get('center_id') or 0), self.alpha_id)
        self.assertEqual(int(response_beta_1.json().get('center_id') or 0), self.beta_id)

    def test_localhost_uses_default_center(self):
        response = self.client.get('/private', headers={'host': 'localhost:8000'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(response.json().get('center_id') or 0), self.default_center_id)

    def test_loopback_ip_uses_default_center(self):
        response = self.client.get('/private', headers={'host': '127.0.0.1:8000'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(response.json().get('center_id') or 0), self.default_center_id)

    def test_alpha_localhost_resolves_subdomain(self):
        response = self.client.get('/private', headers={'host': 'alpha.localhost:8000'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(response.json().get('center_id') or 0), self.alpha_id)

    def test_local_dotted_hostname_falls_back_to_default(self):
        response = self.client.get('/private', headers={'host': 'desktop-user.mshome.net:8000'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(response.json().get('center_id') or 0), self.default_center_id)

    def test_default_center_auto_created_when_missing(self):
        db = self._session_factory()
        try:
            db.query(Center).filter(Center.slug == 'default-center').delete()
            db.commit()
        finally:
            db.close()

        response = self.client.get('/private', headers={'host': 'localhost:8000'})
        self.assertEqual(response.status_code, 200)

        db = self._session_factory()
        try:
            recreated = db.query(Center).filter(Center.slug == 'default-center').first()
            self.assertIsNotNone(recreated)
            self.assertEqual(int(response.json().get('center_id') or 0), int(recreated.id))
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
