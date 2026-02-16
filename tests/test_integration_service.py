import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.cache import cache
from app.db import Base
from app.models import Center, CenterIntegration
from app.services.integration_service import is_connected, require_integration, upsert_integration


class IntegrationServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / "test_integration_service.db"
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

    @classmethod
    def tearDownClass(cls):
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        db = self._session_factory()
        try:
            cache.invalidate_prefix("integration_status")
            db.query(CenterIntegration).delete()
            db.query(Center).delete()
            db.commit()
        finally:
            db.close()

    def test_require_integration_flags_missing_provider(self):
        db = self._session_factory()
        try:
            center = Center(name="Center A", slug="center-a", timezone="Asia/Kolkata")
            db.add(center)
            db.commit()
            db.refresh(center)

            gate = require_integration(db, "whatsapp", center_id=center.id)
            self.assertTrue(gate.get("integration_required"))
            self.assertEqual(gate.get("provider"), "whatsapp")
        finally:
            db.close()

    def test_connected_provider_unblocks_feature(self):
        db = self._session_factory()
        try:
            center = Center(name="Center A", slug="center-a", timezone="Asia/Kolkata")
            db.add(center)
            db.commit()
            db.refresh(center)

            row = upsert_integration(
                db,
                center_id=center.id,
                provider="whatsapp",
                status="connected",
                config_json={"access_token": "abc123"},
            )
            self.assertEqual(row.status, "connected")
            self.assertNotIn("abc123", row.config_json)

            self.assertTrue(is_connected(db, center.id, "whatsapp"))
            gate = require_integration(db, "whatsapp", center_id=center.id)
            self.assertFalse(gate.get("integration_required"))
        finally:
            db.close()

    def test_connection_status_isolated_per_center(self):
        db = self._session_factory()
        try:
            center_a = Center(name="Center A", slug="center-a", timezone="Asia/Kolkata")
            center_b = Center(name="Center B", slug="center-b", timezone="Asia/Kolkata")
            db.add_all([center_a, center_b])
            db.commit()
            db.refresh(center_a)
            db.refresh(center_b)

            upsert_integration(db, center_id=center_a.id, provider="whatsapp", status="connected", config_json={})
            self.assertTrue(is_connected(db, center_a.id, "whatsapp"))
            self.assertFalse(is_connected(db, center_b.id, "whatsapp"))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
