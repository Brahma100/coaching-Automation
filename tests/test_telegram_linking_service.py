import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AuthUser, Batch, Parent, ParentStudentMap, Role, Student, StudentBatchMap
from app.services.telegram_linking_service import process_link_update


class TelegramLinkingServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / "test_telegram_linking.db"
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
            db.query(ParentStudentMap).delete()
            db.query(StudentBatchMap).delete()
            db.query(Student).delete()
            db.query(Parent).delete()
            db.query(Batch).delete()
            db.query(AuthUser).delete()
            db.add(AuthUser(phone="6291717612", role=Role.ADMIN.value, telegram_chat_id=""))
            db.commit()
        finally:
            db.close()

    def test_contact_with_country_code_links_known_user(self):
        update = {
            "message": {
                "chat": {"id": 777001},
                "from": {"id": 7001},
                "contact": {"phone_number": "+91 6291717612", "user_id": 7001},
            }
        }
        db = self._session_factory()
        try:
            with patch("app.services.telegram_linking_service.gateway_send_event", return_value=[{"ok": True}]):
                result = process_link_update(db, update, center_id=1)
            self.assertTrue(result.get("linked"))
            self.assertEqual(result.get("reason"), "contact_verified_linked")
            row = db.query(AuthUser).filter(AuthUser.phone == "6291717612").first()
            self.assertEqual(str(row.telegram_chat_id), "777001")
        finally:
            db.close()

    def test_text_phone_links_known_user(self):
        update = {
            "message": {
                "chat": {"id": 777002},
                "from": {"id": 7002},
                "text": "6291717612",
            }
        }
        db = self._session_factory()
        try:
            with patch("app.services.telegram_linking_service.gateway_send_event", return_value=[{"ok": True}]):
                result = process_link_update(db, update, center_id=1)
            self.assertTrue(result.get("linked"))
            self.assertEqual(result.get("reason"), "text_phone_linked")
            row = db.query(AuthUser).filter(AuthUser.phone == "6291717612").first()
            self.assertEqual(str(row.telegram_chat_id), "777002")
        finally:
            db.close()

    def test_welcome_message_includes_student_batch_joined_and_parent_info(self):
        db = self._session_factory()
        try:
            batch = Batch(name="Batch A", subject="Math")
            db.add(batch)
            db.flush()
            student = Student(name="Raj Jaiswal", guardian_phone="1234567890", batch_id=batch.id, telegram_chat_id="")
            db.add(student)
            db.flush()
            db.add(StudentBatchMap(student_id=student.id, batch_id=batch.id))
            parent = Parent(name="Sanjay Jaiswal", phone="1234567890", telegram_chat_id="")
            db.add(parent)
            db.flush()
            db.add(ParentStudentMap(parent_id=parent.id, student_id=student.id, relation="father"))
            db.commit()

            update = {
                "message": {
                    "chat": {"id": 777003},
                    "from": {"id": 7003},
                    "contact": {"phone_number": "+91 1234567890", "user_id": 7003},
                }
            }
            with patch("app.services.telegram_linking_service.gateway_send_event", return_value=[{"ok": True}]) as gateway_send:
                result = process_link_update(db, update, center_id=1)
            self.assertTrue(result.get("linked"))
            sent_message = gateway_send.call_args.args[1]["message"]
            self.assertIn("Student Details:", sent_message)
            self.assertIn("Batch: Batch A", sent_message)
            self.assertIn("Joined:", sent_message)
            self.assertIn("Parent: Sanjay Jaiswal (1234567890)", sent_message)
        finally:
            db.close()

    def test_start_does_not_ask_phone_when_student_chat_already_linked(self):
        db = self._session_factory()
        try:
            batch = Batch(name="Batch B", subject="Science")
            db.add(batch)
            db.flush()
            student = Student(name="Aman", guardian_phone="1234567890", batch_id=batch.id, telegram_chat_id="777004")
            db.add(student)
            db.commit()

            update = {
                "message": {
                    "chat": {"id": 777004},
                    "from": {"id": 7004},
                    "text": "/start",
                }
            }
            with patch("app.services.telegram_linking_service.gateway_send_event", return_value=[{"ok": True}]) as gateway_send:
                result = process_link_update(db, update, center_id=1)
            self.assertTrue(result.get("linked"))
            self.assertEqual(result.get("reason"), "already_linked")
            sent_message = gateway_send.call_args.args[1]["message"]
            self.assertIn("Your account is linked and ready for notifications.", sent_message)
            self.assertNotIn("Please share your phone number", sent_message)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
