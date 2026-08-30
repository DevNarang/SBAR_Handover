from datetime import datetime, date, time, timedelta

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import false
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import User, Role, UserWardAssignment, ShiftType, AuditLog, ShiftAssignment, Handover, HandoverStatus
from app.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

SUPERINTENDENTS = {Role.medical_superintendent, Role.nursing_superintendent}
REVIEWERS = SUPERINTENDENTS | {Role.hod, Role.nursing_supervisor}
ADMINS = SUPERINTENDENTS


def current_shift(now: datetime | None = None) -> tuple[ShiftType, date]:
    now = now or datetime.utcnow()
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
    if user.role in SUPERINTENDENTS:
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


def get_shift_assignment(db: Session, ward_id: int, shift_type: ShiftType, shift_date: date) -> ShiftAssignment | None:
    return (
        db.query(ShiftAssignment)
        .options(joinedload(ShiftAssignment.nurse), joinedload(ShiftAssignment.assigned_by))
        .filter(
            ShiftAssignment.ward_id == ward_id,
            ShiftAssignment.shift_type == shift_type,
            ShiftAssignment.shift_date == shift_date,
        )
        .first()
    )


def is_rostered_for_shift(db: Session, user: User, ward_id: int, shift_type: ShiftType, shift_date: date) -> bool:
    row = get_shift_assignment(db, ward_id, shift_type, shift_date)
    return bool(row and row.nurse_id == user.id)


def handover_edit_block_reason(db: Session, user: User, h: Handover) -> str | None:
    """Return a reason the SBAR cannot be edited, or None if the author may update it."""
    if h.status == HandoverStatus.accepted:
        return "Accepted handovers are read-only"
    if user.role == Role.nursing_officer:
        if h.author_id != user.id:
            return "You cannot change another nurse's SBAR"
        if h.status in (HandoverStatus.submitted, HandoverStatus.under_review):
            return "Submitted SBAR is locked until a supervisor returns it"
        if not is_rostered_for_shift(db, user, h.admission.ward_id, h.shift_type, h.shift_date):
            return "You are not assigned to this shift"
        return None
    return "Only the nurse who wrote this SBAR can change it"


def assert_can_edit_handover(db: Session, user: User, h: Handover) -> None:
    reason = handover_edit_block_reason(db, user, h)
    if reason:
        raise HTTPException(status_code=403, detail=reason)


def assert_rostered_writer(db: Session, user: User, ward_id: int, shift_type: ShiftType, shift_date: date) -> None:
    row = get_shift_assignment(db, ward_id, shift_type, shift_date)
    if not row:
        raise HTTPException(403, "A supervisor must assign a nursing officer to this shift first")
    if user.role != Role.nursing_officer or row.nurse_id != user.id:
        raise HTTPException(403, "Only the nurse assigned to this shift can write SBARs")
