import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AuthUser, Batch, Parent, ParentStudentMap, Role, RuleConfig, Student, StudentBatchMap
from app.services.batch_management_service import add_schedule, soft_delete_batch, update_schedule
from app.services.student_notification_service import notify_student, resolve_student_notification_chat_id


class StudentNotificationServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / "test_student_notification.db"
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

    @classmethod
    def tearDownClass(cls):
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def test_resolve_chat_id_falls_back_to_auth_user_by_phone(self):
        db = self._session_factory()
        try:
            db.add(AuthUser(phone="1111111111", role=Role.STUDENT.value, telegram_chat_id="chat-auth-1"))
            batch = Batch(name="B1", subject="Math")
            db.add(batch)
            db.flush()
            student = Student(name="S1", guardian_phone="1111111111", batch_id=batch.id, telegram_chat_id="")
            db.add(student)
            db.commit()

            found = resolve_student_notification_chat_id(db, student)
            self.assertEqual(found, "chat-auth-1")
        finally:
            db.close()

    def test_resolve_chat_id_uses_parent_mapping(self):
        db = self._session_factory()
        try:
            batch = Batch(name="B2", subject="Physics")
            db.add(batch)
            db.flush()
            student = Student(name="S2", guardian_phone="2222222222", batch_id=batch.id, telegram_chat_id="")
            db.add(student)
            db.flush()
            parent = Parent(name="P2", phone="9999999999", telegram_chat_id="chat-parent-2")
            db.add(parent)
            db.flush()
            db.add(ParentStudentMap(parent_id=parent.id, student_id=student.id, relation="guardian"))
            db.commit()

            found = resolve_student_notification_chat_id(db, student)
            self.assertEqual(found, "chat-parent-2")
        finally:
            db.close()

    def test_batch_delete_notifies_active_students(self):
        db = self._session_factory()
        try:
            batch = Batch(name="B3", subject="Chem")
            db.add(batch)
            db.flush()
            student = Student(name="S3", guardian_phone="3333333333", batch_id=batch.id, telegram_chat_id="chat-s3")
            db.add(student)
            db.flush()
            db.add(StudentBatchMap(student_id=student.id, batch_id=batch.id, active=True))
            db.commit()

            with patch("app.services.batch_management_service.notify_student") as mocked_notify:
                row = soft_delete_batch(db, batch.id, actor=None)
            self.assertFalse(row.active)
            self.assertTrue(mocked_notify.called)
        finally:
            db.close()

    def test_notify_student_respects_global_lifecycle_toggle(self):
        db = self._session_factory()
        try:
            db.add(RuleConfig(batch_id=None, enable_student_lifecycle_notifications=False))
            batch = Batch(name="B4", subject="Bio")
            db.add(batch)
            db.flush()
            student = Student(name="S4", guardian_phone="4444444444", batch_id=batch.id, telegram_chat_id="chat-s4")
            db.add(student)
            db.commit()

            with patch("app.services.student_notification_service.queue_telegram_by_chat_id") as mocked_queue:
                ok = notify_student(
                    db,
                    student=student,
                    message="msg",
                    notification_type="student_created",
                )
            self.assertFalse(ok)
            mocked_queue.assert_not_called()
        finally:
            db.close()

    def test_notify_student_critical_uses_gateway_send(self):
        db = self._session_factory()
        try:
            batch = Batch(name="B5", subject="Math")
            db.add(batch)
            db.flush()
            student = Student(name="S5", guardian_phone="5555555555", batch_id=batch.id, telegram_chat_id="chat-s5")
            db.add(student)
            db.commit()

            with patch(
                "app.services.student_notification_service.gateway_send_event",
                return_value=[{"ok": True, "status": "sent"}],
            ) as mocked_gateway, patch("app.services.student_notification_service.queue_telegram_by_chat_id") as mocked_queue:
                ok = notify_student(
                    db,
                    student=student,
                    message="critical msg",
                    notification_type="student_profile_updated",
                    critical=True,
                )

            self.assertTrue(ok)
            mocked_gateway.assert_called_once()
            mocked_queue.assert_not_called()
        finally:
            db.close()

    def test_notify_student_critical_marks_failed_when_gateway_fails(self):
        db = self._session_factory()
        try:
            batch = Batch(name="B6", subject="Math")
            db.add(batch)
            db.flush()
            student = Student(name="S6", guardian_phone="6666666666", batch_id=batch.id, telegram_chat_id="chat-s6")
            db.add(student)
            db.commit()

            with patch(
                "app.services.student_notification_service.gateway_send_event",
                return_value=[{"ok": False, "status": "failed"}],
            ) as mocked_gateway:
                ok = notify_student(
                    db,
                    student=student,
                    message="fallback msg",
                    notification_type="student_profile_updated",
                    critical=True,
                )

            self.assertFalse(ok)
            mocked_gateway.assert_called_once()
        finally:
            db.close()

    def test_update_schedule_notifies_active_batch_students(self):
        db = self._session_factory()
        try:
            batch = Batch(name="B7", subject="Math")
            db.add(batch)
            db.flush()
            student = Student(name="S7", guardian_phone="7777777777", batch_id=batch.id, telegram_chat_id="chat-s7")
            db.add(student)
            db.flush()
            db.add(StudentBatchMap(student_id=student.id, batch_id=batch.id, active=True))
            db.commit()

            schedule = add_schedule(
                db,
                batch.id,
                weekday=1,
                start_time="07:00",
                duration_minutes=60,
                actor=None,
            )
            with patch("app.services.batch_management_service.notify_student") as mocked_notify:
                update_schedule(
                    db,
                    schedule.id,
                    weekday=2,
                    start_time="08:00",
                    duration_minutes=75,
                    actor=None,
                )
            self.assertTrue(mocked_notify.called)
            _, kwargs = mocked_notify.call_args
            self.assertEqual(kwargs.get("notification_type"), "student_batch_schedule_change")
            self.assertIn("Old:", kwargs.get("message", ""))
            self.assertIn("New:", kwargs.get("message", ""))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
