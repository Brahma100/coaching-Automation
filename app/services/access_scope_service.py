from __future__ import annotations

from sqlalchemy import false
from sqlalchemy.orm import Query, Session

from app.core.phone import normalize_phone as _core_normalize_phone
from app.models import AuthUser, Parent, ParentStudentMap, Role, Student, TeacherBatchMap
from app.services.center_scope_service import apply_center_scope, get_actor_center_id


def get_teacher_batch_ids(db: Session, teacher_id: int, *, center_id: int | None = None) -> set[int]:
    clean_teacher_id = int(teacher_id or 0)
    if clean_teacher_id <= 0:
        return set()
    query = db.query(TeacherBatchMap.batch_id).filter(TeacherBatchMap.teacher_id == clean_teacher_id)
    clean_center_id = int(center_id or 0)
    if clean_center_id <= 0:
        teacher_user = db.query(AuthUser).filter(AuthUser.id == clean_teacher_id).first()
        clean_center_id = int(teacher_user.center_id or 0) if teacher_user else 0
    if clean_center_id > 0:
        query = query.filter(TeacherBatchMap.center_id == clean_center_id)
    rows = query.distinct().all()
    return {int(batch_id) for (batch_id,) in rows if batch_id is not None}


def _normalize_phone(value: str) -> str:
    # DEPRECATED: use app.core.phone.normalize_phone directly.
    return _core_normalize_phone(value)


def _resolve_student_ids_for_user(db: Session, user: dict) -> set[int]:
    center_id = int(get_actor_center_id(user) or 0)
    explicit_student_id = int(user.get('student_id') or 0)
    if explicit_student_id > 0:
        return {explicit_student_id}

    phone = _normalize_phone(user.get('phone') or '')
    if not phone:
        return set()

    student_query = db.query(Student.id).filter(Student.guardian_phone == phone)
    if center_id > 0:
        student_query = student_query.filter(Student.center_id == center_id)
    direct_ids = {
        int(student_id)
        for (student_id,) in student_query.all()
        if student_id is not None
    }
    parent_ids = {
        int(parent_id)
        for (parent_id,) in db.query(Parent.id).filter(Parent.phone == phone).all()
        if parent_id is not None
    }
    linked_ids = set()
    if parent_ids:
        linked_ids = {
            int(student_id)
            for (student_id,) in db.query(ParentStudentMap.student_id).filter(ParentStudentMap.parent_id.in_(parent_ids)).all()
            if student_id is not None
        }
    return direct_ids.union(linked_ids)


def apply_batch_scope(query: Query, user: dict):
    query = apply_center_scope(query, user)
    role = (user.get('role') or '').strip().lower()
    if role == Role.ADMIN.value:
        return query

    db = query.session
    if db is None:
        return query

    entity = None
    if query.column_descriptions:
        entity = query.column_descriptions[0].get('entity')
    if entity is None:
        return query

    if role == Role.TEACHER.value:
        teacher_id = int(user.get('user_id') or 0)
        batch_ids = get_teacher_batch_ids(db, teacher_id, center_id=get_actor_center_id(user))
        if not batch_ids:
            return query.filter(false())
        if hasattr(entity, 'batch_id'):
            return query.filter(entity.batch_id.in_(batch_ids))
        if getattr(entity, '__tablename__', '') == 'batches' and hasattr(entity, 'id'):
            return query.filter(entity.id.in_(batch_ids))
        return query.filter(false())

    if role == Role.STUDENT.value:
        student_ids = _resolve_student_ids_for_user(db, user)
        if not student_ids:
            return query.filter(false())
        if hasattr(entity, 'student_id'):
            return query.filter(entity.student_id.in_(student_ids))
        if getattr(entity, '__tablename__', '') == 'students' and hasattr(entity, 'id'):
            return query.filter(entity.id.in_(student_ids))
        return query.filter(false())

    return query.filter(false())
