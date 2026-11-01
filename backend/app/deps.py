from datetime import datetime, date, time, timedelta

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import false
from sqlalchemy.orm import Session, joinedload

from app.clock import now as ist_now
from app.config import settings
from app.database import get_db
from app.models import (
    User,
    Role,
    UserWardAssignment,
    ShiftType,
    AuditLog,
    ShiftAssignment,
    PatientShiftAssignment,
    Handover,
    HandoverStatus,
)
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

SUPERINTENDENTS = {Role.medical_superintendent, Role.nursing_superintendent}
REVIEWERS = SUPERINTENDENTS | {Role.hod, Role.nursing_supervisor}
ADMINS = SUPERINTENDENTS
HOSPITAL_WIDE = SUPERINTENDENTS | {Role.nursing_supervisor}
PATIENT_ASSIGNERS = {Role.hod, Role.nursing_supervisor, Role.medical_superintendent}
ASSIGNABLE_ROLES = {Role.nursing_officer, Role.hod, Role.nursing_supervisor, Role.medical_superintendent}


def current_shift(now: datetime | None = None) -> tuple[ShiftType, date]:
    now = now or ist_now()
    hour = now.hour
    if settings.morning_start <= hour < settings.morning_end:
        return ShiftType.morning, now.date()
    if settings.afternoon_start <= hour < settings.afternoon_end:
        return ShiftType.afternoon, now.date()
    shift_date = now.date() if hour >= settings.evening_start else now.date() - timedelta(days=1)
    return ShiftType.evening, shift_date


def previous_shift(shift_type: ShiftType, shift_date: date) -> tuple[ShiftType, date]:
    if shift_type == ShiftType.morning:
        return ShiftType.evening, shift_date - timedelta(days=1)
    if shift_type == ShiftType.afternoon:
        return ShiftType.morning, shift_date
    return ShiftType.afternoon, shift_date


def next_shift(shift_type: ShiftType, shift_date: date) -> tuple[ShiftType, date]:
    if shift_type == ShiftType.morning:
        return ShiftType.afternoon, shift_date
    if shift_type == ShiftType.afternoon:
        return ShiftType.evening, shift_date
    return ShiftType.morning, shift_date + timedelta(days=1)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return user


def require_roles(*roles: Role):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return checker


def user_ward_ids(db: Session, user: User) -> list[int]:
    if user.role in HOSPITAL_WIDE:
        from app.models import Ward

        return [w.id for w in db.query(Ward).filter(Ward.is_active.is_(True)).all()]
    rows = db.query(UserWardAssignment).filter(UserWardAssignment.user_id == user.id).all()
    ids = [r.ward_id for r in rows]
    if user.role == Role.hod and user.department:
        from app.models import Ward

        dept_ids = [
            w.id
            for w in db.query(Ward).filter(Ward.department == user.department, Ward.is_active.is_(True)).all()
        ]
        return sorted(set(ids + dept_ids))
    return ids


def ward_filter(column, ids: list[int]):
    if not ids:
        return false()
    return column.in_(ids)


def assert_ward_access(db: Session, user: User, ward_id: int) -> None:
    if ward_id not in user_ward_ids(db, user):
        raise HTTPException(status_code=403, detail="No access to this ward")


def write_audit(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    diff: dict | None = None,
    request: Request | None = None,
) -> None:
    ip = None
    if request and request.client:
        ip = request.client.host
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            diff=diff,
            ip=ip,
        )
    )
    db.commit()


def list_shift_assignments(db: Session, ward_id: int, shift_type: ShiftType, shift_date: date) -> list[ShiftAssignment]:
    return (
        db.query(ShiftAssignment)
        .options(joinedload(ShiftAssignment.nurse), joinedload(ShiftAssignment.assigned_by))
        .filter(
            ShiftAssignment.ward_id == ward_id,
            ShiftAssignment.shift_type == shift_type,
            ShiftAssignment.shift_date == shift_date,
        )
        .order_by(ShiftAssignment.id)
        .all()
    )


def get_shift_assignment(db: Session, ward_id: int, shift_type: ShiftType, shift_date: date) -> ShiftAssignment | None:
    rows = list_shift_assignments(db, ward_id, shift_type, shift_date)
    return rows[0] if rows else None


def get_patient_assignment(
    db: Session, admission_id: int, shift_type: ShiftType, shift_date: date
) -> PatientShiftAssignment | None:
    return (
        db.query(PatientShiftAssignment)
        .options(joinedload(PatientShiftAssignment.nurse))
        .filter(
            PatientShiftAssignment.admission_id == admission_id,
            PatientShiftAssignment.shift_type == shift_type,
            PatientShiftAssignment.shift_date == shift_date,
        )
        .first()
    )


def is_rostered_for_shift(db: Session, user: User, ward_id: int, shift_type: ShiftType, shift_date: date) -> bool:
    return any(row.nurse_id == user.id for row in list_shift_assignments(db, ward_id, shift_type, shift_date))


def nurse_can_write_patient(
    db: Session, user: User, ward_id: int, shift_type: ShiftType, shift_date: date, admission_id: int
) -> bool:
    if user.role != Role.nursing_officer:
        return False
    if not is_rostered_for_shift(db, user, ward_id, shift_type, shift_date):
        return False
    assigned = get_patient_assignment(db, admission_id, shift_type, shift_date)
    if assigned and assigned.nurse_id != user.id:
        return False
    return True


def handover_edit_block_reason(db: Session, user: User, h: Handover) -> str | None:
    """Return a reason the SBAR cannot be edited, or None if this nurse may update it."""
    if h.status == HandoverStatus.accepted:
        return "Accepted handovers are read-only"
    if user.role != Role.nursing_officer:
        return "Only the nurse who wrote this SBAR can change it"
    if h.status in (HandoverStatus.submitted, HandoverStatus.under_review):
        return "Submitted SBAR is locked until a supervisor returns it"
    ward_id = h.admission.ward_id
    if not is_rostered_for_shift(db, user, ward_id, h.shift_type, h.shift_date):
        return "You are not assigned to this shift"
    assigned = get_patient_assignment(db, h.admission_id, h.shift_type, h.shift_date)
    if assigned and assigned.nurse_id != user.id:
        return "This patient is assigned to another nurse for this shift"
    if assigned and assigned.nurse_id == user.id:
        return None
    if h.author_id != user.id:
        return "You cannot change another nurse's SBAR"
    return None


def assert_can_edit_handover(db: Session, user: User, h: Handover) -> None:
    reason = handover_edit_block_reason(db, user, h)
    if reason:
        raise HTTPException(status_code=403, detail=reason)


def assert_rostered_writer(
    db: Session, user: User, ward_id: int, shift_type: ShiftType, shift_date: date, admission_id: int
) -> None:
    rows = list_shift_assignments(db, ward_id, shift_type, shift_date)
    if not rows:
        raise HTTPException(403, "A supervisor must assign a nursing officer to this shift first")
    if not nurse_can_write_patient(db, user, ward_id, shift_type, shift_date, admission_id):
        assigned = get_patient_assignment(db, admission_id, shift_type, shift_date)
        if assigned and assigned.nurse_id != user.id:
            raise HTTPException(403, "This patient is assigned to another nurse for this shift")
        raise HTTPException(403, "Only a nurse rostered on this shift can write SBARs")
