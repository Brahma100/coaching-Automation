import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import router_guard
from app.db import Base, get_db
from app.models import (
    AuthUser,
    Batch,
    Center,
    ClassSession,
    Parent,
    Student,
    TeacherBatchMap,
)
from app.routers import attendance, class_session, communications, parents, referral


class RouterScopeEnforcementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_router_scope_enforcement.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

        cls._orig_validate = router_guard.validate_session_token

        def fake_validate_session_token(token: str | None):
            if token == 'token-admin-c1':
                return {'user_id': 1, 'role': 'admin', 'center_id': 1}
            if token == 'token-teacher-c1':
                return {'user_id': 10, 'role': 'teacher', 'center_id': 1}
            if token == 'token-teacher-c2':
                return {'user_id': 20, 'role': 'teacher', 'center_id': 2}
            return None

        router_guard.validate_session_token = fake_validate_session_token

        app = FastAPI()
        app.include_router(class_session.router)
        app.include_router(communications.router)
        app.include_router(parents.router)
        app.include_router(referral.router)
        app.include_router(attendance.router)

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
        router_guard.validate_session_token = cls._orig_validate
        cls.client.close()
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        db = self._session_factory()
        try:
            db.query(TeacherBatchMap).delete()
            db.query(ClassSession).delete()
            db.query(Parent).delete()
            db.query(Student).delete()
            db.query(Batch).delete()
            db.query(AuthUser).delete()
            db.query(Center).delete()

            c1 = Center(id=1, name='Center 1', slug='center-1')
            c2 = Center(id=2, name='Center 2', slug='center-2')
            admin = AuthUser(id=1, phone='9000000001', role='admin', center_id=1)
            teacher1 = AuthUser(id=10, phone='9000000010', role='teacher', center_id=1)
            teacher2 = AuthUser(id=20, phone='9000000020', role='teacher', center_id=2)
            batch1 = Batch(id=101, name='Batch-C1', subject='Math', start_time='09:00', active=True, center_id=1)
            batch2 = Batch(id=202, name='Batch-C2', subject='Science', start_time='10:00', active=True, center_id=2)
            student1 = Student(id=1001, name='Student-C1', guardian_phone='9111111111', batch_id=101, center_id=1)
            student2 = Student(id=2002, name='Student-C2', guardian_phone='9222222222', batch_id=202, center_id=2)
            parent = Parent(id=501, name='Parent-1', phone='9333333333')
            session1 = ClassSession(
                id=701,
                batch_id=101,
                subject='Math',
                scheduled_start=datetime.utcnow(),
                duration_minutes=60,
                teacher_id=10,
                center_id=1,
                status='open',
            )
            session2 = ClassSession(
                id=702,
                batch_id=202,
                subject='Science',
                scheduled_start=datetime.utcnow(),
                duration_minutes=60,
                teacher_id=20,
                center_id=2,
                status='open',
            )

            db.add_all([c1, c2, admin, teacher1, teacher2, batch1, batch2, student1, student2, parent, session1, session2])
            db.add_all(
                [
                    TeacherBatchMap(teacher_id=10, batch_id=101, center_id=1, is_primary=True),
                    TeacherBatchMap(teacher_id=20, batch_id=202, center_id=2, is_primary=True),
                ]
            )
            db.commit()
        finally:
            db.close()

    def _headers(self, token: str) -> dict:
        return {'Authorization': f'Bearer {token}'}

    def test_teacher_cannot_create_session_for_another_center_batch(self):
        response = self.client.post(
            '/class-sessions/create',
            headers=self._headers('token-teacher-c1'),
            json={
                'batch_id': 202,
                'subject': 'Science',
                'scheduled_start': datetime.utcnow().isoformat(),
                'topic_planned': '',
                'teacher_id': 10,
                'duration_minutes': 60,
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_start_session_not_in_mapped_batch_scope(self):
        response = self.client.post('/class-sessions/start/702', headers=self._headers('token-teacher-c1'))
        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_notify_student_from_other_teacher_batch(self):
        response = self.client.post(
            '/communications/notify/student/2002',
            headers=self._headers('token-teacher-c1'),
            params={'message': 'Hi'},
        )
        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_link_parent_to_student_outside_scope(self):
        response = self.client.post(
            '/parents/link-student',
            headers=self._headers('token-teacher-c1'),
            json={'parent_id': 501, 'student_id': 2002, 'relation': 'guardian'},
        )
        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_submit_attendance_for_other_teacher_batch(self):
        response = self.client.post(
            '/attendance/submit',
            headers=self._headers('token-teacher-c1'),
            json={
                'batch_id': 202,
                'attendance_date': date.today().isoformat(),
                'records': [{'student_id': 2002, 'status': 'Present', 'comment': ''}],
                'subject': 'Science',
                'teacher_id': 20,
                'topic_planned': '',
                'topic_completed': '',
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_operate_within_center_scope(self):
        create_session = self.client.post(
            '/class-sessions/create',
            headers=self._headers('token-admin-c1'),
            json={
                'batch_id': 101,
                'subject': 'Math',
                'scheduled_start': datetime.utcnow().isoformat(),
                'topic_planned': 'Algebra',
                'teacher_id': 10,
                'duration_minutes': 60,
            },
        )
        self.assertEqual(create_session.status_code, 200)

        start_session = self.client.post('/class-sessions/start/701', headers=self._headers('token-admin-c1'))
        self.assertEqual(start_session.status_code, 200)

        notify = self.client.post(
            '/communications/notify/student/1001',
            headers=self._headers('token-admin-c1'),
            params={'message': 'Reminder'},
        )
        self.assertEqual(notify.status_code, 200)

        link_parent = self.client.post(
            '/parents/link-student',
            headers=self._headers('token-admin-c1'),
            json={'parent_id': 501, 'student_id': 1001, 'relation': 'guardian'},
        )
        self.assertEqual(link_parent.status_code, 200)

        create_referral = self.client.post(
            '/referral/create',
            headers=self._headers('token-admin-c1'),
            json={'student_id': 1001},
        )
        self.assertEqual(create_referral.status_code, 200)

    def test_cross_center_access_always_forbidden(self):
        response = self.client.post(
            '/referral/create',
            headers=self._headers('token-admin-c1'),
            json={'student_id': 2002},
        )
        self.assertEqual(response.status_code, 403)

    def test_parent_cannot_be_linked_across_centers(self):
        db = self._session_factory()
        try:
            parent_center_2 = Parent(name='Parent-C2', phone='9444444444', center_id=2)
            db.add(parent_center_2)
            db.commit()
            db.refresh(parent_center_2)
            parent_id = int(parent_center_2.id)
        finally:
            db.close()

        response = self.client.post(
            '/parents/link-student',
            headers=self._headers('token-admin-c1'),
            json={'parent_id': parent_id, 'student_id': 1001, 'relation': 'guardian'},
        )
        self.assertEqual(response.status_code, 403)

    def test_parent_created_in_center_a_cannot_link_to_student_in_center_b(self):
        created = self.client.post(
            '/parents/create',
            headers=self._headers('token-admin-c1'),
            json={'name': 'Parent-C1-New', 'phone': '9555555555', 'telegram_chat_id': ''},
        )
        self.assertEqual(created.status_code, 200)
        parent_id = int(created.json()['id'])

        link_cross_center = self.client.post(
            '/parents/link-student',
            headers=self._headers('token-admin-c1'),
            json={'parent_id': parent_id, 'student_id': 2002, 'relation': 'guardian'},
        )
        self.assertEqual(link_cross_center.status_code, 403)

    def test_admin_creates_parent_only_in_own_center(self):
        created = self.client.post(
            '/parents/create',
            headers=self._headers('token-admin-c1'),
            json={'name': 'Scoped Parent', 'phone': '9666666666', 'telegram_chat_id': ''},
        )
        self.assertEqual(created.status_code, 200)
        parent_id = int(created.json()['id'])

        db = self._session_factory()
        try:
            row = db.query(Parent).filter(Parent.id == parent_id).first()
            self.assertIsNotNone(row)
            self.assertEqual(int(row.center_id), 1)
        finally:
            db.close()

    def test_db_level_parent_center_is_populated(self):
        for idx in range(2):
            response = self.client.post(
                '/parents/create',
                headers=self._headers('token-admin-c1'),
                json={'name': f'Parent-{idx}', 'phone': f'97777777{idx:02d}', 'telegram_chat_id': ''},
            )
            self.assertEqual(response.status_code, 200)

        db = self._session_factory()
        try:
            rows = db.query(Parent).all()
            self.assertTrue(rows)
            self.assertTrue(all(int(getattr(row, 'center_id', 0) or 0) > 0 for row in rows))
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
