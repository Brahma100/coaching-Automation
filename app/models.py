from datetime import date, datetime, time
from enum import Enum
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Role(str, Enum):
    ADMIN = 'admin'
    TEACHER = 'teacher'
    STUDENT = 'student'


class AllowedUserStatus(str, Enum):
    INVITED = 'invited'
    ACTIVE = 'active'
    DISABLED = 'disabled'


class Center(Base):
    __tablename__ = 'centers'
    __table_args__ = (
        UniqueConstraint('slug', name='uq_centers_slug'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(180), default='default-center')
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey('auth_users.id'), nullable=True, index=True)
    timezone: Mapped[str] = mapped_column(String(60), default='Asia/Kolkata')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class CenterIntegration(Base):
    __tablename__ = 'center_integrations'
    __table_args__ = (
        UniqueConstraint('center_id', 'provider', name='uq_center_integrations_center_provider'),
        Index('ix_center_integrations_center_provider', 'center_id', 'provider'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey('centers.id'), index=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(20), default='disconnected', index=True)
    config_json: Mapped[str] = mapped_column(Text, default='')
    connected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class OnboardingState(Base):
    __tablename__ = 'onboarding_states'
    __table_args__ = (
        UniqueConstraint('center_id', name='uq_onboarding_states_center_id'),
        UniqueConstraint('reserved_slug', name='uq_onboarding_states_reserved_slug'),
        Index('ix_onboarding_states_status_completed', 'status', 'is_completed'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey('centers.id'), index=True)
    temp_slug: Mapped[str] = mapped_column(String(120), default='', index=True)
    reserved_slug: Mapped[str] = mapped_column(String(120), index=True)
    setup_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default='in_progress', index=True)
    current_step: Mapped[str] = mapped_column(String(40), default='center_setup', index=True)
    payload_json: Mapped[str] = mapped_column(Text, default='{}')
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    lock_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class Batch(Base):
    __tablename__ = 'batches'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    start_time: Mapped[str] = mapped_column(String(10), default='07:00')
    subject: Mapped[str] = mapped_column(String(120), default='General', index=True)
    academic_level: Mapped[str] = mapped_column(String(20), default='')
    color_code: Mapped[str] = mapped_column(String(16), default='#2f7bf6')
    default_duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_students: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    meeting_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    room_id: Mapped[int | None] = mapped_column(ForeignKey('rooms.id'), nullable=True, index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey('centers.id'), default=1, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    students: Mapped[list['Student']] = relationship('Student', back_populates='batch')
    schedules: Mapped[list['BatchSchedule']] = relationship('BatchSchedule', back_populates='batch')
    student_links: Mapped[list['StudentBatchMap']] = relationship('StudentBatchMap', back_populates='batch')
    teacher_links: Mapped[list['TeacherBatchMap']] = relationship('TeacherBatchMap', back_populates='batch')
    class_sessions: Mapped[list['ClassSession']] = relationship('ClassSession', back_populates='batch')
    room: Mapped['Room | None'] = relationship('Room', back_populates='batches')
    program_links: Mapped[list['BatchProgram']] = relationship('BatchProgram', back_populates='batch', cascade='all, delete-orphan')
    board_links: Mapped[list['BatchBoard']] = relationship('BatchBoard', back_populates='batch', cascade='all, delete-orphan')
    level_links: Mapped[list['BatchLevel']] = relationship('BatchLevel', back_populates='batch', cascade='all, delete-orphan')
    subject_links: Mapped[list['BatchSubject']] = relationship('BatchSubject', back_populates='batch', cascade='all, delete-orphan')
    programs: Mapped[list['Program']] = relationship('Program', secondary='batch_programs', back_populates='batches')
    boards: Mapped[list['Board']] = relationship('Board', secondary='batch_boards', back_populates='batches')
    levels: Mapped[list['ClassLevel']] = relationship('ClassLevel', secondary='batch_levels', back_populates='batches')
    subjects: Mapped[list['Subject']] = relationship('Subject', secondary='batch_subjects', back_populates='batches')
    note_links: Mapped[list['NoteBatch']] = relationship(
        'NoteBatch',
        back_populates='batch',
        cascade='all, delete-orphan',
        overlaps='notes,batches',
    )
    notes: Mapped[list['Note']] = relationship(
        'Note',
        secondary='note_batches',
        back_populates='batches',
        overlaps='note_links,batch_links,batch,note',
    )


class Program(Base):
    __tablename__ = 'programs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    batch_links: Mapped[list['BatchProgram']] = relationship('BatchProgram', back_populates='program', cascade='all, delete-orphan')
    batches: Mapped[list['Batch']] = relationship('Batch', secondary='batch_programs', back_populates='programs')


class Board(Base):
    __tablename__ = 'boards'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    shortcode: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    batch_links: Mapped[list['BatchBoard']] = relationship('BatchBoard', back_populates='board', cascade='all, delete-orphan')
    batches: Mapped[list['Batch']] = relationship('Batch', secondary='batch_boards', back_populates='boards')


class ClassLevel(Base):
    __tablename__ = 'class_levels'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    min_grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    batch_links: Mapped[list['BatchLevel']] = relationship('BatchLevel', back_populates='class_level', cascade='all, delete-orphan')
    batches: Mapped[list['Batch']] = relationship('Batch', secondary='batch_levels', back_populates='levels')


class Subject(Base):
    __tablename__ = 'subjects'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    code: Mapped[str] = mapped_column(String(20), default='', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    batch_links: Mapped[list['BatchSubject']] = relationship('BatchSubject', back_populates='subject', cascade='all, delete-orphan')
    batches: Mapped[list['Batch']] = relationship('Batch', secondary='batch_subjects', back_populates='subjects')
    chapters: Mapped[list['Chapter']] = relationship('Chapter', back_populates='subject', cascade='all, delete-orphan')
    notes: Mapped[list['Note']] = relationship('Note', back_populates='subject')


class Chapter(Base):
    __tablename__ = 'chapters'
    __table_args__ = (
        UniqueConstraint('subject_id', 'name', name='uq_chapter_subject_name'),
        Index('ix_chapters_subject_name', 'subject_id', 'name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey('subjects.id'), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    subject: Mapped['Subject'] = relationship('Subject', back_populates='chapters')
    topics: Mapped[list['Topic']] = relationship('Topic', back_populates='chapter', cascade='all, delete-orphan')
    notes: Mapped[list['Note']] = relationship('Note', back_populates='chapter')


class Topic(Base):
    __tablename__ = 'topics'
    __table_args__ = (
        Index('ix_topics_chapter_parent_name', 'chapter_id', 'parent_topic_id', 'name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey('chapters.id'), index=True)
    parent_topic_id: Mapped[int | None] = mapped_column(ForeignKey('topics.id'), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    chapter: Mapped['Chapter'] = relationship('Chapter', back_populates='topics')
    parent_topic: Mapped['Topic | None'] = relationship('Topic', remote_side='Topic.id', back_populates='child_topics')
    child_topics: Mapped[list['Topic']] = relationship('Topic', back_populates='parent_topic')
    notes: Mapped[list['Note']] = relationship('Note', back_populates='topic')


class Note(Base):
    __tablename__ = 'notes'
    __table_args__ = (
        Index('ix_notes_subject_topic_created', 'subject_id', 'topic_id', 'created_at'),
        Index('ix_notes_release_expire', 'release_at', 'expire_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default='')
    subject_id: Mapped[int] = mapped_column(ForeignKey('subjects.id'), index=True)
    chapter_id: Mapped[int | None] = mapped_column(ForeignKey('chapters.id'), nullable=True, index=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey('topics.id'), nullable=True, index=True)
    drive_file_id: Mapped[str] = mapped_column(String(255), index=True)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(120), default='application/pdf')
    uploaded_by: Mapped[int] = mapped_column(Integer, index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey('centers.id'), default=1, index=True)
    visible_to_students: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    visible_to_parents: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    release_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    expire_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    subject: Mapped['Subject'] = relationship('Subject', back_populates='notes')
    chapter: Mapped['Chapter | None'] = relationship('Chapter', back_populates='notes')
    topic: Mapped['Topic | None'] = relationship('Topic', back_populates='notes')
    batch_links: Mapped[list['NoteBatch']] = relationship(
        'NoteBatch',
        back_populates='note',
        cascade='all, delete-orphan',
        overlaps='notes,batches',
    )
    batches: Mapped[list['Batch']] = relationship(
        'Batch',
        secondary='note_batches',
        back_populates='notes',
        overlaps='note_links,batch_links,batch,note',
    )
    tag_links: Mapped[list['NoteTag']] = relationship(
        'NoteTag',
        back_populates='note',
        cascade='all, delete-orphan',
        overlaps='notes,tags',
    )
    tags: Mapped[list['Tag']] = relationship(
        'Tag',
        secondary='note_tags',
        back_populates='notes',
        overlaps='tag_links,note_links,note,tag',
    )
    versions: Mapped[list['NoteVersion']] = relationship(
        'NoteVersion',
        back_populates='note',
        cascade='all, delete-orphan',
        order_by='NoteVersion.version_number.desc()',
    )
    download_logs: Mapped[list['NoteDownloadLog']] = relationship('NoteDownloadLog', back_populates='note', cascade='all, delete-orphan')


class NoteBatch(Base):
    __tablename__ = 'note_batches'
    __table_args__ = (
        UniqueConstraint('note_id', 'batch_id', name='uq_note_batch_note_batch'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    note_id: Mapped[int] = mapped_column(ForeignKey('notes.id'), index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('batches.id'), index=True)

    note: Mapped['Note'] = relationship('Note', back_populates='batch_links', overlaps='batches,notes')
    batch: Mapped['Batch'] = relationship('Batch', back_populates='note_links', overlaps='batches,notes')


class Tag(Base):
    __tablename__ = 'tags'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    note_links: Mapped[list['NoteTag']] = relationship(
        'NoteTag',
        back_populates='tag',
        cascade='all, delete-orphan',
        overlaps='notes,tags',
    )
    notes: Mapped[list['Note']] = relationship(
        'Note',
        secondary='note_tags',
        back_populates='tags',
        overlaps='tag_links,note_links,note,tag',
    )


class NoteTag(Base):
    __tablename__ = 'note_tags'
    __table_args__ = (
        UniqueConstraint('note_id', 'tag_id', name='uq_note_tag_note_tag'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    note_id: Mapped[int] = mapped_column(ForeignKey('notes.id'), index=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey('tags.id'), index=True)

    note: Mapped['Note'] = relationship('Note', back_populates='tag_links', overlaps='notes,tags')
    tag: Mapped['Tag'] = relationship('Tag', back_populates='note_links', overlaps='notes,tags')


class NoteVersion(Base):
    __tablename__ = 'note_versions'
    __table_args__ = (
        UniqueConstraint('note_id', 'version_number', name='uq_note_version_note_number'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    note_id: Mapped[int] = mapped_column(ForeignKey('notes.id'), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, index=True)
    drive_file_id: Mapped[str] = mapped_column(String(255), index=True)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String(120), default='application/pdf')
    uploaded_by: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    note: Mapped['Note'] = relationship('Note', back_populates='versions')


class NoteDownloadLog(Base):
    __tablename__ = 'note_download_logs'
    __table_args__ = (
        Index('ix_note_download_logs_note_student', 'note_id', 'student_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    note_id: Mapped[int] = mapped_column(ForeignKey('notes.id'), index=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey('students.id'), nullable=True, index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey('batches.id'), nullable=True, index=True)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    ip_address: Mapped[str] = mapped_column(String(64), default='')
    user_agent: Mapped[str] = mapped_column(String(255), default='')

    note: Mapped['Note'] = relationship('Note', back_populates='download_logs')


class BatchProgram(Base):
    __tablename__ = 'batch_programs'
    __table_args__ = (UniqueConstraint('batch_id', 'program_id', name='uq_batch_program_batch_program'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('batches.id'), index=True)
    program_id: Mapped[int] = mapped_column(ForeignKey('programs.id'), index=True)

    batch: Mapped['Batch'] = relationship('Batch', back_populates='program_links')
    program: Mapped['Program'] = relationship('Program', back_populates='batch_links')


class BatchBoard(Base):
    __tablename__ = 'batch_boards'
    __table_args__ = (UniqueConstraint('batch_id', 'board_id', name='uq_batch_board_batch_board'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('batches.id'), index=True)
    board_id: Mapped[int] = mapped_column(ForeignKey('boards.id'), index=True)

    batch: Mapped['Batch'] = relationship('Batch', back_populates='board_links')
    board: Mapped['Board'] = relationship('Board', back_populates='batch_links')


class BatchLevel(Base):
    __tablename__ = 'batch_levels'
    __table_args__ = (UniqueConstraint('batch_id', 'class_level_id', name='uq_batch_level_batch_class'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('batches.id'), index=True)
    class_level_id: Mapped[int] = mapped_column(ForeignKey('class_levels.id'), index=True)

    batch: Mapped['Batch'] = relationship('Batch', back_populates='level_links')
    class_level: Mapped['ClassLevel'] = relationship('ClassLevel', back_populates='batch_links')


class BatchSubject(Base):
    __tablename__ = 'batch_subjects'
    __table_args__ = (UniqueConstraint('batch_id', 'subject_id', name='uq_batch_subject_batch_subject'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('batches.id'), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey('subjects.id'), index=True)

    batch: Mapped['Batch'] = relationship('Batch', back_populates='subject_links')
    subject: Mapped['Subject'] = relationship('Subject', back_populates='batch_links')


class Student(Base):
    __tablename__ = 'students'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    guardian_phone: Mapped[str] = mapped_column(String(20), default='')
    telegram_chat_id: Mapped[str] = mapped_column(String(40), default='')
    batch_id: Mapped[int] = mapped_column(ForeignKey('batches.id'), index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey('centers.id'), default=1, index=True)
    enable_daily_digest: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    enable_homework_reminders: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    enable_motivation_messages: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    preferred_contact_method: Mapped[str] = mapped_column(String(20), default='telegram')
    language_preference: Mapped[str] = mapped_column(String(20), default='en')

    batch: Mapped['Batch'] = relationship('Batch', back_populates='students')
    batch_links: Mapped[list['StudentBatchMap']] = relationship('StudentBatchMap', back_populates='student')
    attendances: Mapped[list['AttendanceRecord']] = relationship('AttendanceRecord', back_populates='student')
    fees: Mapped[list['FeeRecord']] = relationship('FeeRecord', back_populates='student')
    homework_submissions: Mapped[list['HomeworkSubmission']] = relationship('HomeworkSubmission', back_populates='student')
    referrals: Mapped[list['ReferralCode']] = relationship('ReferralCode', back_populates='student')
    parent_links: Mapped[list['ParentStudentMap']] = relationship('ParentStudentMap', back_populates='student')
    risk_profile: Mapped['StudentRiskProfile | None'] = relationship('StudentRiskProfile', back_populates='student', uselist=False)
    risk_events: Mapped[list['StudentRiskEvent']] = relationship('StudentRiskEvent', back_populates='student')


class AttendanceRecord(Base):
    __tablename__ = 'attendance_records'
    __table_args__ = (
        Index('ix_attendance_records_student_date', 'student_id', 'attendance_date'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'))
    attendance_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str] = mapped_column(Text, default='')
    marked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped['Student'] = relationship('Student', back_populates='attendances')


class FeeRecord(Base):
    __tablename__ = 'fee_records'
    __table_args__ = (
        Index('ix_fee_records_student_due_paid', 'student_id', 'due_date', 'is_paid'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'))
    due_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Float)
    paid_amount: Mapped[float] = mapped_column(Float, default=0)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    upi_link: Mapped[str] = mapped_column(String(255), default='')

    student: Mapped['Student'] = relationship('Student', back_populates='fees')


class Homework(Base):
    __tablename__ = 'homework'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default='')
    due_date: Mapped[date] = mapped_column(Date)
    attachment_path: Mapped[str] = mapped_column(String(255), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    submissions: Mapped[list['HomeworkSubmission']] = relationship('HomeworkSubmission', back_populates='homework')


class HomeworkSubmission(Base):
    __tablename__ = 'homework_submissions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    homework_id: Mapped[int] = mapped_column(ForeignKey('homework.id'))
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'))
    file_path: Mapped[str] = mapped_column(String(255), default='')
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    homework: Mapped['Homework'] = relationship('Homework', back_populates='submissions')
    student: Mapped['Student'] = relationship('Student', back_populates='homework_submissions')


class ReferralCode(Base):
    __tablename__ = 'referral_codes'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'))
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    reward_points: Mapped[int] = mapped_column(Integer, default=0)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped['Student'] = relationship('Student', back_populates='referrals')


class Offer(Base):
    __tablename__ = 'offers'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(140))
    discount_type: Mapped[str] = mapped_column(String(20), default='flat')  # flat | percent
    discount_value: Mapped[float] = mapped_column(Float, default=0)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    redemptions: Mapped[list['OfferRedemption']] = relationship('OfferRedemption', back_populates='offer')


class OfferRedemption(Base):
    __tablename__ = 'offer_redemptions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey('offers.id'))
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'))
    fee_record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    referral_code_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_amount: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    offer: Mapped['Offer'] = relationship('Offer', back_populates='redemptions')


class ClassSession(Base):
    __tablename__ = 'class_sessions'
    __table_args__ = (
        Index('ix_class_sessions_batch_scheduled_start', 'batch_id', 'scheduled_start'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('batches.id'), index=True)
    subject: Mapped[str] = mapped_column(String(80), default='General')
    scheduled_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    actual_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    topic_planned: Mapped[str] = mapped_column(Text, default='')
    topic_completed: Mapped[str] = mapped_column(Text, default='')
    teacher_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey('centers.id'), default=1, index=True)
    status: Mapped[str] = mapped_column(String(20), default='scheduled')  # scheduled|open|submitted|closed|missed (legacy: running|completed)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    post_class_processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    post_class_error: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    batch: Mapped['Batch'] = relationship('Batch', back_populates='class_sessions')


class BatchSchedule(Base):
    __tablename__ = 'batch_schedules'
    __table_args__ = (
        Index('ix_batch_schedules_weekday_start_time', 'weekday', 'start_time'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('batches.id'), index=True)
    weekday: Mapped[int] = mapped_column(Integer, index=True)  # Monday=0 ... Sunday=6
    start_time: Mapped[str] = mapped_column(String(5))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    batch: Mapped['Batch'] = relationship('Batch', back_populates='schedules')


class StudentBatchMap(Base):
    __tablename__ = 'student_batch_map'
    __table_args__ = (
        Index('ix_student_batch_map_batch_active', 'batch_id', 'active'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'), index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('batches.id'), index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    student: Mapped['Student'] = relationship('Student', back_populates='batch_links')
    batch: Mapped['Batch'] = relationship('Batch', back_populates='student_links')


class TeacherBatchMap(Base):
    __tablename__ = 'teacher_batch_map'
    __table_args__ = (
        UniqueConstraint('teacher_id', 'batch_id', name='uq_teacher_batch_map_teacher_batch'),
        Index('ix_teacher_batch_map_teacher_batch', 'teacher_id', 'batch_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey('auth_users.id'), index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('batches.id'), index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey('centers.id'), default=1, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    teacher: Mapped['AuthUser'] = relationship('AuthUser', back_populates='teacher_batch_links')
    batch: Mapped['Batch'] = relationship('Batch', back_populates='teacher_links')


class Parent(Base):
    __tablename__ = 'parents'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey('centers.id'), default=1, index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20), default='')
    telegram_chat_id: Mapped[str] = mapped_column(String(40), default='')

    center: Mapped['Center'] = relationship('Center')
    student_links: Mapped[list['ParentStudentMap']] = relationship('ParentStudentMap', back_populates='parent')


class ParentStudentMap(Base):
    __tablename__ = 'parent_student_map'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey('parents.id'), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'), index=True)
    relation: Mapped[str] = mapped_column(String(30), default='guardian')

    parent: Mapped['Parent'] = relationship('Parent', back_populates='student_links')
    student: Mapped['Student'] = relationship('Student', back_populates='parent_links')


class ActionToken(Base):
    __tablename__ = 'action_tokens'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    action_type: Mapped[str] = mapped_column(String(40), index=True)
    expected_role: Mapped[str] = mapped_column(String(20), default='teacher', index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey('centers.id'), default=1, index=True)
    payload_json: Mapped[str] = mapped_column(Text, default='{}')
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    issued_ip: Mapped[str] = mapped_column(String(64), default='')
    issued_user_agent: Mapped[str] = mapped_column(String(512), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RuleConfig(Base):
    __tablename__ = 'rule_configs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    absence_streak_threshold: Mapped[int] = mapped_column(Integer, default=3)
    notify_parent_on_absence: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_parent_on_fee_due: Mapped[bool] = mapped_column(Boolean, default=True)
    enable_student_lifecycle_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_grace_period_days: Mapped[int] = mapped_column(Integer, default=0)
    quiet_hours_start: Mapped[str] = mapped_column(String(5), default='22:00')
    quiet_hours_end: Mapped[str] = mapped_column(String(5), default='06:00')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PendingAction(Base):
    __tablename__ = 'pending_actions'
    __table_args__ = (
        Index('ix_pending_actions_status_teacher_due', 'status', 'teacher_id', 'due_at'),
        Index('ix_pending_actions_teacher_status', 'teacher_id', 'status'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    type: Mapped[str] = mapped_column(String(30), index=True)  # fee_followup|absence|homework|manual
    action_type: Mapped[str] = mapped_column(String(40), default='', index=True)
    student_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    related_session_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    teacher_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    session_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey('centers.id'), default=1, index=True)
    status: Mapped[str] = mapped_column(String(20), default='open', index=True)  # open|resolved
    note: Mapped[str] = mapped_column(Text, default='')
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution_note: Mapped[str] = mapped_column(Text, default='')
    escalation_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StaffUser(Base):
    __tablename__ = 'staff_users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(20), index=True)  # admin | teacher
    password_hash: Mapped[str] = mapped_column(String(255), default='')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuthUser(Base):
    __tablename__ = 'auth_users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(20), default=Role.TEACHER.value, index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey('centers.id'), default=1, index=True)
    first_login_completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_otp: Mapped[str] = mapped_column(String(255), default='')
    otp_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), default='')
    telegram_chat_id: Mapped[str] = mapped_column(String(80), default='', index=True)
    google_sub: Mapped[str] = mapped_column(String(255), default='', index=True)
    notification_delete_minutes: Mapped[int] = mapped_column(Integer, default=15)
    enable_auto_delete_notes_on_expiry: Mapped[bool] = mapped_column(Boolean, default=False)
    ui_toast_duration_seconds: Mapped[int] = mapped_column(Integer, default=5)
    time_zone: Mapped[str] = mapped_column(String(60), default='UTC')
    timezone: Mapped[str] = mapped_column(String(60), default='Asia/Kolkata')
    daily_work_start_time: Mapped[time] = mapped_column(Time, default=time(hour=7, minute=0))
    daily_work_end_time: Mapped[time] = mapped_column(Time, default=time(hour=20, minute=0))
    max_daily_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calendar_preferences: Mapped[str] = mapped_column(Text, default='{}')
    calendar_view_preference: Mapped[str] = mapped_column(String(20), default='week')
    calendar_snap_minutes: Mapped[int] = mapped_column(Integer, default=15)
    enable_live_mode_auto_open: Mapped[bool] = mapped_column(Boolean, default=True)
    default_event_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    teacher_batch_links: Mapped[list['TeacherBatchMap']] = relationship('TeacherBatchMap', back_populates='teacher')


class TeacherCommunicationSettings(Base):
    __tablename__ = 'teacher_communication_settings'
    __table_args__ = (
        UniqueConstraint('teacher_id', name='uq_teacher_communication_settings_teacher'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey('auth_users.id'), index=True)
    provider: Mapped[str] = mapped_column(String(20), default='telegram')
    provider_config_json: Mapped[str] = mapped_column(Text, default='')
    enabled_events: Mapped[str] = mapped_column(Text, default='[]')
    quiet_hours: Mapped[str] = mapped_column(Text, default='{"start":"22:00","end":"06:00"}')
    delete_timer_minutes: Mapped[int] = mapped_column(Integer, default=15)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TeacherAutomationRule(Base):
    __tablename__ = 'teacher_automation_rules'
    __table_args__ = (
        UniqueConstraint('teacher_id', name='uq_teacher_automation_rules_teacher'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey('auth_users.id'), index=True)
    notify_on_attendance: Mapped[bool] = mapped_column(Boolean, default=True)
    class_start_reminder: Mapped[bool] = mapped_column(Boolean, default=True)
    fee_due_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    student_absence_escalation: Mapped[bool] = mapped_column(Boolean, default=True)
    homework_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DriveOAuthToken(Base):
    __tablename__ = 'drive_oauth_tokens'
    __table_args__ = (
        UniqueConstraint('user_id', name='uq_drive_oauth_token_user'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    refresh_token: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class AllowedUser(Base):
    __tablename__ = 'allowed_users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(20), default=Role.TEACHER.value, index=True)
    status: Mapped[str] = mapped_column(String(20), default=AllowedUserStatus.INVITED.value, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BackupLog(Base):
    __tablename__ = 'backup_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default='failed', index=True)  # success | failed
    message: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CommunicationLog(Base):
    __tablename__ = 'communication_logs'
    __table_args__ = (
        UniqueConstraint('teacher_id', 'session_id', 'notification_type', name='uq_comm_logs_teacher_session_type'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    teacher_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    session_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    channel: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='queued')
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delete_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    notification_type: Mapped[str] = mapped_column(String(40), default='', index=True)
    event_type: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    delivery_status: Mapped[str] = mapped_column(String(30), default='pending', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AutomationFailureLog(Base):
    __tablename__ = 'automation_failure_logs'
    __table_args__ = (
        Index('ix_automation_failure_logs_center_job_created', 'center_id', 'job_name', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey('centers.id'), default=1, index=True)
    job_name: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(50), default='', index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    error_message: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ProviderCircuitState(Base):
    __tablename__ = 'provider_circuit_states'
    __table_args__ = (
        UniqueConstraint('center_id', 'provider_name', name='uq_provider_circuit_center_provider'),
        Index('ix_provider_circuit_center_provider', 'center_id', 'provider_name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey('centers.id'), default=1, index=True)
    provider_name: Mapped[str] = mapped_column(String(30), default='telegram', index=True)
    state: Mapped[str] = mapped_column(String(20), default='closed', index=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_state_change_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RateLimitState(Base):
    __tablename__ = 'rate_limit_states'
    __table_args__ = (
        UniqueConstraint('center_id', 'scope_type', 'scope_key', 'action_name', name='uq_rate_limit_scope_action'),
        Index('ix_rate_limit_scope_action', 'center_id', 'scope_type', 'scope_key', 'action_name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey('centers.id'), default=1, index=True)
    scope_type: Mapped[str] = mapped_column(String(20), default='user', index=True)
    scope_key: Mapped[str] = mapped_column(String(120), default='', index=True)
    action_name: Mapped[str] = mapped_column(String(80), default='', index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)


class StudentRiskProfile(Base):
    __tablename__ = 'student_risk_profiles'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'), unique=True, index=True)
    attendance_score: Mapped[float] = mapped_column(Float, default=1.0)
    homework_score: Mapped[float] = mapped_column(Float, default=1.0)
    fee_score: Mapped[float] = mapped_column(Float, default=1.0)
    test_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_risk_score: Mapped[float] = mapped_column(Float, default=100.0, index=True)
    risk_level: Mapped[str] = mapped_column(String(10), default='LOW', index=True)
    last_computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    student: Mapped['Student'] = relationship('Student', back_populates='risk_profile')


class StudentRiskEvent(Base):
    __tablename__ = 'student_risk_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('students.id'), index=True)
    previous_risk_level: Mapped[str | None] = mapped_column(String(10), nullable=True)
    new_risk_level: Mapped[str] = mapped_column(String(10), index=True)
    reason_json: Mapped[str] = mapped_column(Text, default='{}')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    student: Mapped['Student'] = relationship('Student', back_populates='risk_events')


class TeacherTodaySnapshot(Base):
    __tablename__ = 'teacher_today_snapshot'

    teacher_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class AdminOpsSnapshot(Base):
    __tablename__ = 'admin_ops_snapshot'

    center_id: Mapped[int] = mapped_column(ForeignKey('centers.id'), default=1, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class StudentDashboardSnapshot(Base):
    __tablename__ = 'student_dashboard_snapshot'

    student_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class Room(Base):
    __tablename__ = 'rooms'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    institute_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    name: Mapped[str] = mapped_column(String(120))
    capacity: Mapped[int] = mapped_column(Integer, default=0)
    color_code: Mapped[str] = mapped_column(String(16), default='#94a3b8')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    batches: Mapped[list['Batch']] = relationship('Batch', back_populates='room')


class CalendarOverride(Base):
    __tablename__ = 'calendar_overrides'
    __table_args__ = (
        Index('ix_calendar_overrides_batch_date', 'batch_id', 'override_date'),
        Index('ix_calendar_overrides_date_batch', 'override_date', 'batch_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    institute_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('batches.id'), index=True)
    override_date: Mapped[date] = mapped_column(Date, index=True)
    new_start_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    new_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reason: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    batch: Mapped['Batch'] = relationship('Batch')


class CalendarHoliday(Base):
    __tablename__ = 'calendar_holidays'
    __table_args__ = (
        UniqueConstraint('country_code', 'holiday_date', 'name', name='uq_calendar_holidays_country_date_name'),
        Index('ix_calendar_holidays_country_date', 'country_code', 'holiday_date'),
        Index('ix_calendar_holidays_year_country', 'year', 'country_code'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    country_code: Mapped[str] = mapped_column(String(2), default='IN', index=True)
    holiday_date: Mapped[date] = mapped_column(Date, index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(180))
    local_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    source: Mapped[str] = mapped_column(String(40), default='nager')
    is_national: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class TeacherUnavailability(Base):
    __tablename__ = 'teacher_unavailability'
    __table_args__ = (
        Index('ix_teacher_unavailability_teacher_date', 'teacher_id', 'date'),
        Index('ix_teacher_unavailability_teacher_date_start', 'teacher_id', 'date', 'start_time'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    teacher_id: Mapped[int] = mapped_column(Integer, index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    reason: Mapped[str] = mapped_column(String(255), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
