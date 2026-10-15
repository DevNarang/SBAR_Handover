from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AccountStatus, Role, User, LoginAttempt, Ward
from app.schemas import LoginRequest, SignupRequest, Token, UserOut
from app.security import verify_password, create_access_token, hash_password
from app.deps import get_current_user, user_ward_ids, write_audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/signup-options")
def signup_options(db: Session = Depends(get_db)):
    wards = db.query(Ward).filter(Ward.is_active.is_(True)).order_by(Ward.name).all()
    departments = sorted({(w.department or "").strip() for w in wards if (w.department or "").strip()})
    extra = {
        (u.department or "").strip()
        for u in db.query(User).filter(User.role == Role.hod, User.department.isnot(None)).all()
        if (u.department or "").strip()
    }
    departments = sorted(set(departments) | extra)
    return {
        "departments": departments,
        "wards": [{"id": w.id, "name": w.name, "department": w.department} for w in wards],
    }


@router.post("/signup")
def signup(body: SignupRequest, request: Request, db: Session = Depends(get_db)):
    if body.password != body.confirm_password:
        raise HTTPException(400, "Passwords do not match")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    kind = (body.kind or "").strip().lower()
    if kind not in {"department_admin", "nurse"}:
        raise HTTPException(400, "Choose Department Admin or Nurse")

    email = (body.email or "").strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Enter a valid official email")
    employee_id = body.employee_id.strip()
    if db.query(User).filter((User.email == email) | (User.employee_id == employee_id)).first():
        raise HTTPException(400, "Email or employee ID already exists")

    department = (body.department or body.new_department or "").strip()
    ward_id = body.ward_id
    if kind == "department_admin":
        if not department:
            raise HTTPException(400, "Select a department or request a new one")
        if not (body.designation or "").strip():
            raise HTTPException(400, "Designation is required")
        role = Role.hod
        ward_id = None
    else:
        if not ward_id:
            raise HTTPException(400, "Select your ward / unit")
        ward = db.get(Ward, ward_id)
        if not ward or not ward.is_active:
            raise HTTPException(400, "Ward not found")
        department = (body.department or ward.department or "").strip()
        if body.department and ward.department and body.department.strip() != ward.department.strip():
            raise HTTPException(400, "Ward does not belong to that department")
        role = Role.nursing_officer

    user = User(
        email=email,
        employee_id=employee_id,
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
        role=role,
        department=department or None,
        mobile=body.mobile.strip(),
        designation=(body.designation or "").strip() or None,
        account_status=AccountStatus.pending,
        requested_ward_id=ward_id,
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    write_audit(db, None, "signup", "user", user.id, request=request)
    queue = "super_admin" if kind == "department_admin" else "department_admin"
    return {
        "id": user.id,
        "account_status": user.account_status,
        "queue": queue,
        "submitted_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/login")
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ident = body.identifier.strip().lower()
    attempt = db.query(LoginAttempt).filter(LoginAttempt.identifier == ident).first()
    if attempt and attempt.locked_until and attempt.locked_until > datetime.utcnow():
        raise HTTPException(status_code=423, detail="Account locked. Try again in 15 minutes.")

    user = (
        db.query(User)
        .filter((User.email == ident) | (User.employee_id == body.identifier.strip()))
        .first()
    )
    if not user:
        user = db.query(User).filter(User.email == body.identifier.strip()).first()

    password_ok = bool(user and verify_password(body.password, user.password_hash))
    if not user or not password_ok:
        if not attempt:
            attempt = LoginAttempt(identifier=ident, failed_count=0)
            db.add(attempt)
        attempt.failed_count += 1
        if attempt.failed_count >= 5:
            attempt.locked_until = datetime.utcnow() + timedelta(minutes=15)
            attempt.failed_count = 0
        db.commit()
        write_audit(db, None, "login_failed", "user", ident, request=request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if attempt:
        attempt.failed_count = 0
        attempt.locked_until = None
        db.commit()

    status_value = user.account_status or AccountStatus.approved
    if status_value == AccountStatus.pending:
        write_audit(db, user, "login_pending", "user", user.id, request=request)
        raise HTTPException(
            status_code=403,
            detail={
                "code": "pending",
                "message": "Your request is awaiting approval. You cannot use the portal yet.",
                "queue": "super_admin" if user.role == Role.hod else "department_admin",
                "submitted_at": user.created_at.isoformat() if user.created_at else None,
            },
        )
    if status_value == AccountStatus.rejected:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "rejected",
                "message": "Your request was rejected.",
                "reason": user.rejection_reason or "Contact your administrator.",
            },
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    write_audit(db, user, "login", "user", user.id, request=request)
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    out = UserOut.model_validate(user)
    out.ward_ids = user_ward_ids(db, user)
    return out
