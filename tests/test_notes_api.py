import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.cache import cache, cache_key
from app.db import Base, get_db
from app.models import (
    Batch,
    Chapter,
    Note,
    NoteBatch,
    NoteDownloadLog,
    NoteTag,
    NoteVersion,
    Student,
    StudentBatchMap,
    Subject,
    Tag,
    Topic,
)
from app.routers import notes as notes_router
from app.services.drive_oauth_service import DriveNotConnectedError
from app.services.google_drive_service import DriveStreamPayload


PDF_BYTES = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n'


class NotesApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(cls._tmpdir.name) / 'test_notes_api.db'
        cls._engine = create_engine(f"sqlite:///{db_path}", connect_args={'check_same_thread': False})
        cls._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
        Base.metadata.create_all(bind=cls._engine)

        cls._orig_validate_session_token = notes_router.validate_session_token
        cls._orig_require_student_session = notes_router.require_student_session
        cls._orig_upload_note_pdf = notes_router.upload_note_pdf
        cls._orig_stream_file = notes_router.stream_file
        cls._orig_delete_file = notes_router.delete_file

        def fake_validate_session_token(token: str | None):
            if token == 'token-teacher':
                return {'user_id': 101, 'phone': '9000000001', 'role': 'teacher'}
            if token == 'token-admin':
                return {'user_id': 102, 'phone': '9000000002', 'role': 'admin'}
            if token in ('token-student-1', 'token-student-2'):
                return {'user_id': 201, 'phone': '9000000010', 'role': 'student'}
            return None

        def fake_require_student_session(db, token: str | None):
            if token == 'token-student-1':
                student = db.query(Student).filter(Student.name == 'Student A').first()
                return {'session': fake_validate_session_token(token), 'student': student}
            if token == 'token-student-2':
                student = db.query(Student).filter(Student.name == 'Student B').first()
                return {'session': fake_validate_session_token(token), 'student': student}
            raise PermissionError('Unauthorized')

        cls._upload_counter = 0

        def fake_upload_note_pdf(file_bytes: bytes, filename: str, mime_type: str, user_id: int):
            cls._upload_counter += 1
            return {'file_id': f'drive-file-{cls._upload_counter}', 'web_view_link': None}

        def fake_stream_file(file_id: str, user_id: int | None = None):
            return DriveStreamPayload(
                chunks=iter([PDF_BYTES]),
                mime_type='application/pdf',
                file_size=len(PDF_BYTES),
                filename=f'{file_id}.pdf',
            )

        cls._deleted_drive_ids = []

        def fake_delete_file(file_id: str, user_id: int | None = None):
            cls._deleted_drive_ids.append((file_id, user_id))

        notes_router.validate_session_token = fake_validate_session_token
        notes_router.require_student_session = fake_require_student_session
        notes_router.upload_note_pdf = fake_upload_note_pdf
        notes_router.stream_file = fake_stream_file
        notes_router.delete_file = fake_delete_file

        app = FastAPI()
        app.include_router(notes_router.router)

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
        notes_router.validate_session_token = cls._orig_validate_session_token
        notes_router.require_student_session = cls._orig_require_student_session
        notes_router.upload_note_pdf = cls._orig_upload_note_pdf
        notes_router.stream_file = cls._orig_stream_file
        notes_router.delete_file = cls._orig_delete_file
        cls.client.close()
        cls._engine.dispose()
        cls._tmpdir.cleanup()

    def setUp(self):
        db = self._session_factory()
        try:
            cache.invalidate_prefix('notes_list')
            cache.invalidate_prefix('notes_analytics')

            for table in (
                NoteDownloadLog,
                NoteVersion,
                NoteTag,
                NoteBatch,
                Note,
                Tag,
                Topic,
                Chapter,
                StudentBatchMap,
                Student,
                Batch,
                Subject,
            ):
                db.query(table).delete()
            db.commit()
            self.__class__._deleted_drive_ids.clear()

            subject = Subject(name='Physics', code='PHY')
            db.add(subject)
            db.commit()
            db.refresh(subject)

            chapter = Chapter(subject_id=subject.id, name='Mechanics')
            db.add(chapter)
            db.commit()
            db.refresh(chapter)

            topic = Topic(chapter_id=chapter.id, name='Kinematics')
            db.add(topic)

            batch_a = Batch(name='Batch A', start_time='07:00', subject='Physics', academic_level='XI')
            batch_b = Batch(name='Batch B', start_time='08:00', subject='Physics', academic_level='XI')
            batch_c = Batch(name='Batch C', start_time='09:00', subject='Physics', academic_level='XI')
            db.add_all([batch_a, batch_b, batch_c])
            db.commit()
            db.refresh(topic)
            db.refresh(batch_a)
            db.refresh(batch_b)
            db.refresh(batch_c)

            student_a = Student(name='Student A', guardian_phone='9000000010', batch_id=batch_a.id)
            student_b = Student(name='Student B', guardian_phone='9000000011', batch_id=batch_c.id)
            db.add_all([student_a, student_b])
            db.commit()
            db.refresh(student_a)
            db.refresh(student_b)

            db.add_all(
                [
                    StudentBatchMap(student_id=student_a.id, batch_id=batch_a.id, active=True),
                    StudentBatchMap(student_id=student_b.id, batch_id=batch_c.id, active=True),
                ]
            )
            db.commit()

            self.subject_id = subject.id
            self.chapter_id = chapter.id
            self.topic_id = topic.id
            self.batch_a_id = batch_a.id
            self.batch_b_id = batch_b.id
            self.batch_c_id = batch_c.id
            self.student_a_id = student_a.id
            self.student_b_id = student_b.id
        finally:
            db.close()

    def _upload_note(self, batch_ids, tags='["algebra"]', note_id=None):
        data = {
            'title': 'Week 1 Notes',
            'description': 'Chapter notes',
            'subject_id': str(self.subject_id),
            'chapter_id': str(self.chapter_id),
            'topic_id': str(self.topic_id),
            'batch_ids': batch_ids,
            'tags': tags,
            'visible_to_students': 'true',
            'visible_to_parents': 'false',
        }
        if note_id is not None:
            data['note_id'] = str(note_id)
        return self.client.post(
            '/api/notes/upload',
            data=data,
            files={'file': ('notes.pdf', PDF_BYTES, 'application/pdf')},
            headers={'Authorization': 'Bearer token-teacher'},
        )

    def test_upload_validation_rejects_non_pdf(self):
        response = self.client.post(
            '/api/notes/upload',
            data={
                'title': 'Invalid upload',
                'subject_id': str(self.subject_id),
                'batch_ids': f'[{self.batch_a_id}]',
            },
            files={'file': ('notes.txt', b'hello world', 'text/plain')},
            headers={'Authorization': 'Bearer token-teacher'},
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_creates_multi_batch_and_tag_links(self):
        response = self._upload_note(batch_ids=f'[{self.batch_a_id}, {self.batch_b_id}]', tags='["revision","weekly"]')
        self.assertEqual(response.status_code, 200)

        db = self._session_factory()
        try:
            note = db.query(Note).first()
            self.assertIsNotNone(note)
            batch_links = db.query(NoteBatch).filter(NoteBatch.note_id == note.id).all()
            self.assertEqual({row.batch_id for row in batch_links}, {self.batch_a_id, self.batch_b_id})

            tag_links = db.query(NoteTag).filter(NoteTag.note_id == note.id).all()
            tag_ids = [row.tag_id for row in tag_links]
            tag_names = {row.name for row in db.query(Tag).filter(Tag.id.in_(tag_ids)).all()}
            self.assertEqual(tag_names, {'revision', 'weekly'})

            versions = db.query(NoteVersion).filter(NoteVersion.note_id == note.id).all()
            self.assertEqual(len(versions), 1)
            self.assertEqual(versions[0].version_number, 1)
        finally:
            db.close()

    def test_download_permission_enforced_for_student(self):
        upload = self._upload_note(batch_ids=f'[{self.batch_a_id}]')
        self.assertEqual(upload.status_code, 200)
        note_id = upload.json()['note']['id']

        denied = self.client.get(
            f'/api/notes/{note_id}/download',
            headers={'Authorization': 'Bearer token-student-2'},
        )
        self.assertEqual(denied.status_code, 403)

    def test_download_creates_log(self):
        upload = self._upload_note(batch_ids=f'[{self.batch_a_id}]')
        self.assertEqual(upload.status_code, 200)
        note_id = upload.json()['note']['id']

        allowed = self.client.get(
            f'/api/notes/{note_id}/download',
            headers={'Authorization': 'Bearer token-student-1'},
        )
        self.assertEqual(allowed.status_code, 200)

        db = self._session_factory()
        try:
            logs = db.query(NoteDownloadLog).filter(NoteDownloadLog.note_id == note_id).all()
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0].student_id, self.student_a_id)
            self.assertEqual(logs[0].batch_id, self.batch_a_id)
        finally:
            db.close()

    def test_cache_invalidated_on_upload(self):
        key = cache_key('notes_list', 'teacher:seed')
        cache.set_cached(key, {'items': [{'id': 1}]}, ttl=60)
        self.assertIsNotNone(cache.get_cached(key))

        response = self._upload_note(batch_ids=f'[{self.batch_a_id}]')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(cache.get_cached(key))

    def test_upload_new_version_when_note_id_is_provided(self):
        first = self._upload_note(batch_ids=f'[{self.batch_a_id}]', tags='["v1"]')
        self.assertEqual(first.status_code, 200)
        note_id = first.json()['note']['id']

        second = self._upload_note(batch_ids=f'[{self.batch_a_id}]', tags='["v2"]', note_id=note_id)
        self.assertEqual(second.status_code, 200)

        db = self._session_factory()
        try:
            versions = (
                db.query(NoteVersion)
                .filter(NoteVersion.note_id == note_id)
                .order_by(NoteVersion.version_number.asc())
                .all()
            )
            self.assertEqual([row.version_number for row in versions], [1, 2])
        finally:
            db.close()

    def test_upload_fails_if_drive_not_connected(self):
        original_upload = notes_router.upload_note_pdf

        def fail_upload(*args, **kwargs):
            raise DriveNotConnectedError('Drive not connected. Admin must connect Drive first.')

        notes_router.upload_note_pdf = fail_upload
        try:
            response = self._upload_note(batch_ids=f'[{self.batch_a_id}]')
            self.assertEqual(response.status_code, 400)
            self.assertIn('Drive not connected', response.json().get('detail', ''))
        finally:
            notes_router.upload_note_pdf = original_upload

    def test_update_note_without_file_updates_metadata_only(self):
        upload = self._upload_note(batch_ids=f'[{self.batch_a_id}]', tags='["v1"]')
        self.assertEqual(upload.status_code, 200)
        note_id = upload.json()['note']['id']

        db = self._session_factory()
        try:
            original_note = db.query(Note).filter(Note.id == note_id).first()
            self.assertIsNotNone(original_note)
            original_drive_file_id = original_note.drive_file_id
        finally:
            db.close()

        response = self.client.put(
            f'/api/notes/{note_id}',
            data={
                'title': 'Week 1 Notes Updated',
                'description': 'Updated text',
                'subject_id': str(self.subject_id),
                'chapter_id': str(self.chapter_id),
                'topic_id': str(self.topic_id),
                'batch_ids': f'[{self.batch_a_id}, {self.batch_b_id}]',
                'tags': '["updated","v1"]',
                'visible_to_students': 'true',
                'visible_to_parents': 'true',
            },
            headers={'Authorization': 'Bearer token-teacher'},
        )
        self.assertEqual(response.status_code, 200)

        db = self._session_factory()
        try:
            note = db.query(Note).filter(Note.id == note_id).first()
            self.assertIsNotNone(note)
            self.assertEqual(note.title, 'Week 1 Notes Updated')
            self.assertEqual(note.description, 'Updated text')
            self.assertEqual(note.drive_file_id, original_drive_file_id)

            versions = db.query(NoteVersion).filter(NoteVersion.note_id == note_id).all()
            self.assertEqual(len(versions), 1)
        finally:
            db.close()

    def test_update_note_with_file_replaces_drive_file_and_cleans_old_file(self):
        upload = self._upload_note(batch_ids=f'[{self.batch_a_id}]', tags='["v1"]')
        self.assertEqual(upload.status_code, 200)
        note_id = upload.json()['note']['id']

        db = self._session_factory()
        try:
            original_note = db.query(Note).filter(Note.id == note_id).first()
            self.assertIsNotNone(original_note)
            old_drive_file_id = original_note.drive_file_id
        finally:
            db.close()

        response = self.client.put(
            f'/api/notes/{note_id}',
            data={
                'title': 'Week 1 Notes v2',
                'description': 'Updated with new file',
                'subject_id': str(self.subject_id),
                'chapter_id': str(self.chapter_id),
                'topic_id': str(self.topic_id),
                'batch_ids': f'[{self.batch_a_id}]',
                'tags': '["v2"]',
                'visible_to_students': 'true',
                'visible_to_parents': 'false',
            },
            files={'file': ('notes-v2.pdf', PDF_BYTES, 'application/pdf')},
            headers={'Authorization': 'Bearer token-teacher'},
        )
        self.assertEqual(response.status_code, 200)

        db = self._session_factory()
        try:
            note = db.query(Note).filter(Note.id == note_id).first()
            self.assertIsNotNone(note)
            self.assertNotEqual(note.drive_file_id, old_drive_file_id)
            versions = (
                db.query(NoteVersion)
                .filter(NoteVersion.note_id == note_id)
                .order_by(NoteVersion.version_number.asc())
                .all()
            )
            self.assertEqual([row.version_number for row in versions], [1, 2])
        finally:
            db.close()

        deleted_ids = {row[0] for row in self.__class__._deleted_drive_ids}
        self.assertIn(old_drive_file_id, deleted_ids)

    def test_delete_note_removes_drive_files_and_db_row(self):
        upload = self._upload_note(batch_ids=f'[{self.batch_a_id}]', tags='["v1"]')
        self.assertEqual(upload.status_code, 200)
        note_id = upload.json()['note']['id']

        second = self._upload_note(batch_ids=f'[{self.batch_a_id}]', tags='["v2"]', note_id=note_id)
        self.assertEqual(second.status_code, 200)

        db = self._session_factory()
        try:
            drive_ids = {
                row.drive_file_id
                for row in db.query(NoteVersion).filter(NoteVersion.note_id == note_id).all()
                if row.drive_file_id
            }
            note = db.query(Note).filter(Note.id == note_id).first()
            if note and note.drive_file_id:
                drive_ids.add(note.drive_file_id)
        finally:
            db.close()

        response = self.client.delete(
            f'/api/notes/{note_id}',
            headers={'Authorization': 'Bearer token-teacher'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('ok'))

        db = self._session_factory()
        try:
            note = db.query(Note).filter(Note.id == note_id).first()
            self.assertIsNone(note)
        finally:
            db.close()

        deleted_ids = {row[0] for row in self.__class__._deleted_drive_ids}
        self.assertTrue(drive_ids.issubset(deleted_ids))


if __name__ == '__main__':
    unittest.main()
