from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import AccountStatus, User, Ward, UserWardAssignment, Protocol, Role
from app.schemas import UserCreate, UserUpdate, UserOut, WardIn, WardOut, ProtocolIn
from app.security import hash_password
from app.deps import get_current_user, require_roles, write_audit, ADMINS, SUPERINTENDENTS, user_ward_ids, ward_filter

router = APIRouter(tags=["admin"])


def _user_out(db: Session, user: User) -> UserOut:
    from app.deps import user_ward_ids

    out = UserOut.model_validate(user)
    out.ward_ids = [a.ward_id for a in user.ward_assignments] if user.ward_assignments else []
    if not out.ward_ids:
        out.ward_ids = user_ward_ids(db, user)
    return out


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMINS)),
):
    users = db.query(User).options(joinedload(User.ward_assignments)).all()
    return [_user_out(db, u) for u in users]


@router.post("/users", response_model=UserOut)
def create_user(
    body: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMINS)),
):
    if db.query(User).filter((User.email == body.email) | (User.employee_id == body.employee_id)).first():
        raise HTTPException(400, "Email or employee ID already exists")
    u = User(
        email=body.email.lower(),
        employee_id=body.employee_id,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        role=body.role,
        department=body.department,
        mobile=body.mobile,
        designation=body.designation,
        is_active=body.is_active,
        account_status=AccountStatus.approved if body.is_active else AccountStatus.pending,
    )
    db.add(u)
    db.flush()
    for wid in body.ward_ids:
        db.add(UserWardAssignment(user_id=u.id, ward_id=wid))
    db.commit()
    db.refresh(u)
    write_audit(db, user, "create", "user", u.id, request=request)
    return _user_out(db, u)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMINS)),
):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    data = body.model_dump(exclude_unset=True)
    ward_ids = data.pop("ward_ids", None)
    password = data.pop("password", None)
    for k, v in data.items():
        setattr(u, k, v)
    if password:
        u.password_hash = hash_password(password)
    if ward_ids is not None:
        db.query(UserWardAssignment).filter(UserWardAssignment.user_id == u.id).delete()
        for wid in ward_ids:
            db.add(UserWardAssignment(user_id=u.id, ward_id=wid))
    db.commit()
    db.refresh(u)
    write_audit(db, user, "update", "user", u.id, request=request)
    return _user_out(db, u)


@router.get("/wards", response_model=list[WardOut])
def list_wards(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ids = user_ward_ids(db, user)
    q = db.query(Ward)
    if user.role not in SUPERINTENDENTS:
        q = q.filter(ward_filter(Ward.id, ids))
    return q.order_by(Ward.name).all()


@router.post("/wards", response_model=WardOut)
def create_ward(
    body: WardIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in ADMINS | {Role.hod}:
        raise HTTPException(403, "Insufficient permissions")
    data = body.model_dump()
    data["name"] = (data.get("name") or "").strip()
    if not data["name"]:
        raise HTTPException(400, "Ward name is required")
    if user.role == Role.hod:
        if not (user.department or "").strip():
            raise HTTPException(400, "Your account has no department")
        data["department"] = user.department.strip()
    elif data.get("department"):
        data["department"] = data["department"].strip() or None
    if db.query(Ward).filter(Ward.name == data["name"]).first():
        raise HTTPException(400, "A ward with this name already exists")
    w = Ward(**data)
    db.add(w)
    db.commit()
    db.refresh(w)
    write_audit(db, user, "create", "ward", w.id, request=request)
    return w


@router.patch("/wards/{ward_id}", response_model=WardOut)
def update_ward(
    ward_id: int,
    body: WardIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMINS)),
):
    w = db.get(Ward, ward_id)
    if not w:
        raise HTTPException(404, "Ward not found")
    for k, v in body.model_dump().items():
        setattr(w, k, v)
    db.commit()
    db.refresh(w)
    write_audit(db, user, "update", "ward", w.id, request=request)
    return w


@router.get("/protocols")
def list_protocols(
    ward_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.query(Protocol).order_by(Protocol.created_at.desc()).all()
    if ward_id:
        rows = [p for p in rows if not p.ward_ids or ward_id in p.ward_ids]
    return [
        {
            "id": p.id,
            "title": p.title,
            "body": p.body,
            "ward_ids": p.ward_ids or [],
            "created_at": p.created_at,
        }
        for p in rows
    ]


@router.post("/protocols")
def create_protocol(
    body: ProtocolIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.hod, Role.nursing_superintendent, Role.medical_superintendent)),
):
    p = Protocol(
        title=body.title,
        body=body.body,
        ward_ids=body.ward_ids,
        created_by_id=user.id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    write_audit(db, user, "create", "protocol", p.id, request=request)
    return {"id": p.id, "title": p.title, "body": p.body, "ward_ids": p.ward_ids}
