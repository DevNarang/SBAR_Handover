from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import User, Role, UserWardAssignment, ShiftAssignment, ShiftType
from app.schemas import ShiftAssignmentIn
from app.deps import (
    get_current_user,
    assert_ward_access,
    write_audit,
    REVIEWERS,
    current_shift,
    get_shift_assignment,
    user_ward_ids,
)

router = APIRouter(tags=["roster"])


def _serialize(row: ShiftAssignment) -> dict:
    return {
        "id": row.id,
        "ward_id": row.ward_id,
        "shift_type": row.shift_type.value,
        "shift_date": str(row.shift_date),
        "nurse_id": row.nurse_id,
        "nurse_name": row.nurse.full_name if row.nurse else None,
        "assigned_by_id": row.assigned_by_id,
        "assigned_by_name": row.assigned_by.full_name if row.assigned_by else None,
    }


@router.get("/wards/{ward_id}/officers")
def list_ward_officers(
    ward_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assert_ward_access(db, user, ward_id)
    rows = (
        db.query(User)
        .join(UserWardAssignment, UserWardAssignment.user_id == User.id)
        .filter(
            UserWardAssignment.ward_id == ward_id,
            User.role == Role.nursing_officer,
            User.is_active.is_(True),
        )
        .order_by(User.full_name)
        .all()
    )
    return [{"id": u.id, "full_name": u.full_name, "email": u.email, "employee_id": u.employee_id} for u in rows]


@router.get("/shift-assignments")
def list_assignments(
    ward_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _, today = current_shift()
    start = start or today
    end = end or (today + timedelta(days=2))
    allowed = user_ward_ids(db, user)
    q = (
        db.query(ShiftAssignment)
        .options(joinedload(ShiftAssignment.nurse), joinedload(ShiftAssignment.assigned_by))
        .filter(ShiftAssignment.shift_date >= start, ShiftAssignment.shift_date <= end)
        .filter(ShiftAssignment.ward_id.in_(allowed or [0]))
    )
    if ward_id:
        assert_ward_access(db, user, ward_id)
        q = q.filter(ShiftAssignment.ward_id == ward_id)
    rows = q.order_by(ShiftAssignment.shift_date, ShiftAssignment.shift_type).all()
    return [_serialize(r) for r in rows]


@router.post("/shift-assignments")
def assign_shift(
    body: ShiftAssignmentIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in REVIEWERS:
        raise HTTPException(403, "Supervisors assign nursing officer shifts")
    assert_ward_access(db, user, body.ward_id)
    nurse = db.get(User, body.nurse_id)
    if not nurse or not nurse.is_active or nurse.role != Role.nursing_officer:
        raise HTTPException(400, "Assign a nursing officer")
    linked = (
        db.query(UserWardAssignment)
        .filter(UserWardAssignment.user_id == nurse.id, UserWardAssignment.ward_id == body.ward_id)
        .first()
    )
    if not linked:
        raise HTTPException(400, "That officer is not assigned to this ward")
    row = get_shift_assignment(db, body.ward_id, body.shift_type, body.shift_date)
    if row:
        row.nurse_id = nurse.id
        row.assigned_by_id = user.id
    else:
        row = ShiftAssignment(
            ward_id=body.ward_id,
            shift_type=body.shift_type,
            shift_date=body.shift_date,
            nurse_id=nurse.id,
            assigned_by_id=user.id,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    row = (
        db.query(ShiftAssignment)
        .options(joinedload(ShiftAssignment.nurse), joinedload(ShiftAssignment.assigned_by))
        .filter(ShiftAssignment.id == row.id)
        .first()
    )
    write_audit(db, user, "assign_shift", "shift_assignment", row.id, request=request)
    return _serialize(row)


@router.delete("/shift-assignments/{assignment_id}")
def unassign_shift(
    assignment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in REVIEWERS:
        raise HTTPException(403, "Supervisors assign nursing officer shifts")
    row = db.get(ShiftAssignment, assignment_id)
    if not row:
        raise HTTPException(404, "Assignment not found")
    assert_ward_access(db, user, row.ward_id)
    db.delete(row)
    db.commit()
    write_audit(db, user, "unassign_shift", "shift_assignment", assignment_id, request=request)
    return {"ok": True}
