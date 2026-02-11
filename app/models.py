from datetime import date, datetime
from enum import Enum
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    students: Mapped[list['Student']] = relationship('Student', back_populates='batch')
    schedules: Mapped[list['BatchSchedule']] = relationship('BatchSchedule', back_populates='batch')
    student_links: Mapped[list['StudentBatchMap']] = relationship('StudentBatchMap', back_populates='batch')
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
    status: Mapped[str] = mapped_column(String(20), default='scheduled')  # scheduled|open|submitted|closed|missed (legacy: running|completed)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

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


class Parent(Base):
    __tablename__ = 'parents'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20), default='')
    telegram_chat_id: Mapped[str] = mapped_column(String(40), default='')

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
    payload_json: Mapped[str] = mapped_column(Text, default='{}')
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RuleConfig(Base):
    __tablename__ = 'rule_configs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    absence_streak_threshold: Mapped[int] = mapped_column(Integer, default=3)
    notify_parent_on_absence: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_parent_on_fee_due: Mapped[bool] = mapped_column(Boolean, default=True)
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
    last_otp: Mapped[str] = mapped_column(String(255), default='')
    otp_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), default='')
    google_sub: Mapped[str] = mapped_column(String(255), default='', index=True)
    notification_delete_minutes: Mapped[int] = mapped_column(Integer, default=15)
    time_zone: Mapped[str] = mapped_column(String(60), default='UTC')
    calendar_preferences: Mapped[str] = mapped_column(Text, default='{}')
    calendar_view_preference: Mapped[str] = mapped_column(String(20), default='week')
    calendar_snap_minutes: Mapped[int] = mapped_column(Integer, default=15)
    enable_live_mode_auto_open: Mapped[bool] = mapped_column(Boolean, default=True)
    default_event_color: Mapped[str | None] = mapped_column(String(20), nullable=True)


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
