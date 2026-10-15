from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user, write_audit
from app.models import AccountStatus, Role, User, UserWardAssignment, Ward
from app.schemas import RejectRequest

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _out(db: Session, user: User) -> dict:
    ward_name = None
    if user.requested_ward_id:
        ward = db.get(Ward, user.requested_ward_id)
        ward_name = ward.name if ward else None
    return {
        "id": user.id,
        "email": user.email,
        "employee_id": user.employee_id,
        "full_name": user.full_name,
        "role": user.role.value,
        "department": user.department,
        "mobile": user.mobile,
        "designation": user.designation,
        "account_status": user.account_status,
        "rejection_reason": user.rejection_reason,
        "requested_ward_id": user.requested_ward_id,
        "ward_name": ward_name,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "ward_ids": [a.ward_id for a in user.ward_assignments],
    }


def _filter_search(rows: list[User], q: str | None) -> list[User]:
    if not q or not q.strip():
        return rows
    needle = q.strip().lower()
    found = []
    for u in rows:
        blob = " ".join(
            [
                u.full_name or "",
                u.email or "",
                u.employee_id or "",
                u.department or "",
                u.mobile or "",
            ]
        ).lower()
        if needle in blob:
            found.append(u)
    return found


def _status_filter(status: str | None) -> str:
    allowed = {AccountStatus.pending, AccountStatus.approved, AccountStatus.rejected}
    value = (status or AccountStatus.pending).strip().lower()
    if value not in allowed:
        raise HTTPException(400, "Invalid status")
    return value


@router.get("/admins")
def list_admin_requests(
    status: str = AccountStatus.pending,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != Role.nursing_superintendent:
        raise HTTPException(403, "Only the Super Admin can review department admins")
    st = _status_filter(status)
    rows = (
        db.query(User)
        .options(joinedload(User.ward_assignments))
        .filter(User.role == Role.hod, User.account_status == st)
        .order_by(User.created_at.desc())
        .all()
    )
    rows = _filter_search(rows, q)
    return {"status": st, "count": len(rows), "items": [_out(db, u) for u in rows]}


@router.get("/nurses")
def list_nurse_requests(
    status: str = AccountStatus.pending,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in {Role.hod, Role.nursing_superintendent}:
        raise HTTPException(403, "Insufficient permissions")
    st = _status_filter(status)
    query = db.query(User).options(joinedload(User.ward_assignments)).filter(
        User.role == Role.nursing_officer, User.account_status == st
    )
    if user.role == Role.hod:
        if not user.department:
            return {"status": st, "count": 0, "items": []}
        query = query.filter(User.department == user.department)
    rows = query.order_by(User.created_at.desc()).all()
    if q and q.strip():
        needle = q.strip().lower()
        kept = []
        for u in rows:
            ward = db.get(Ward, u.requested_ward_id) if u.requested_ward_id else None
            blob = " ".join(
                [u.full_name or "", u.employee_id or "", u.email or "", u.mobile or "", ward.name if ward else ""]
            ).lower()
            if needle in blob:
                kept.append(u)
        rows = kept
    return {"status": st, "count": len(rows), "items": [_out(db, u) for u in rows]}


def _load_target(db: Session, user_id: int) -> User:
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "Request not found")
    return target


@router.post("/{user_id}/approve")
def approve_request(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    target = _load_target(db, user_id)
    if target.account_status != AccountStatus.pending:
        raise HTTPException(400, "This request is not pending")
    if target.role == Role.hod:
        if user.role != Role.nursing_superintendent:
            raise HTTPException(403, "Only the Super Admin can approve department admins")
    elif target.role == Role.nursing_officer:
        if user.role == Role.hod:
            if not user.department or target.department != user.department:
                raise HTTPException(403, "You can only approve nurses in your department")
        elif user.role != Role.nursing_superintendent:
            raise HTTPException(403, "Insufficient permissions")
        if target.requested_ward_id:
            exists = (
                db.query(UserWardAssignment)
                .filter(
                    UserWardAssignment.user_id == target.id,
                    UserWardAssignment.ward_id == target.requested_ward_id,
                )
                .first()
            )
            if not exists:
                db.add(UserWardAssignment(user_id=target.id, ward_id=target.requested_ward_id))
    else:
        raise HTTPException(400, "This account is not a sign-up request")

    target.account_status = AccountStatus.approved
    target.is_active = True
    target.rejection_reason = None
    db.commit()
    db.refresh(target)
    write_audit(db, user, "approve_signup", "user", target.id, request=request)
    return _out(db, target)


@router.post("/{user_id}/reject")
def reject_request(
    user_id: int,
    body: RejectRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    target = _load_target(db, user_id)
    if target.account_status != AccountStatus.pending:
        raise HTTPException(400, "This request is not pending")
    if target.role == Role.hod:
        if user.role != Role.nursing_superintendent:
            raise HTTPException(403, "Only the Super Admin can reject department admins")
    elif target.role == Role.nursing_officer:
        if user.role == Role.hod:
            if not user.department or target.department != user.department:
                raise HTTPException(403, "You can only reject nurses in your department")
        elif user.role != Role.nursing_superintendent:
            raise HTTPException(403, "Insufficient permissions")
    else:
        raise HTTPException(400, "This account is not a sign-up request")

    target.account_status = AccountStatus.rejected
    target.is_active = False
    target.rejection_reason = body.reason.strip()
    db.commit()
    db.refresh(target)
    write_audit(db, user, "reject_signup", "user", target.id, request=request)
    return _out(db, target)
