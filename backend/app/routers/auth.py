from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import get_db
from app.models import User, LoginAttempt
from app.schemas import LoginRequest, Token, UserOut
from app.security import verify_password, create_access_token
from app.deps import get_current_user, user_ward_ids, write_audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
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

    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
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

    write_audit(db, user, "login", "user", user.id, request=request)
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    out = UserOut.model_validate(user)
    out.ward_ids = user_ward_ids(db, user)
    return out
