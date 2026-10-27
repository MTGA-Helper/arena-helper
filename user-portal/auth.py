from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import Base, engine, ensure_user_profile_columns, get_db
from email_service import create_verification_token, send_verification_email
from models import User
from schemas import (
    DisplayPlayerIdChange,
    AccountDelete,
    PasswordChange,
    Token,
    UserCreate,
    UserLogin,
    UserProfile,
)
from security import hash_password, verify_password

logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)
ensure_user_profile_columns()

router = APIRouter(tags=["auth"])
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be configured")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(email: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        {"sub": email, "exp": expires_at}, SECRET_KEY, algorithm=ALGORITHM
    )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except JWTError:
        email = None
    user = db.query(User).filter(User.email == email).first() if email else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.mtg_player_id == user.mtg_player_id).first():
        raise HTTPException(status_code=400, detail="MTG Arena Player ID already registered")

    new_user = User(
        email=user.email,
        hashed_password=hash_password(user.password),
        mtg_player_id=user.mtg_player_id,
        display_player_id=user.display_player_id,
    )
    token, token_hash, expires_at = create_verification_token()
    new_user.verification_token_hash = token_hash
    new_user.verification_expires_at = expires_at
    db.add(new_user)
    try:
        send_verification_email(user.email, token)
        db.commit()
    except RuntimeError as error:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        db.rollback()
        logger.exception("Verification email delivery failed")
        raise HTTPException(
            status_code=503, detail="Email delivery is currently unavailable"
        ) from error
    return {"message": "Account created. Check your email to verify your address before logging in."}


@router.post("/login", response_model=Token)
def login_for_access_token(
    user_credentials: UserLogin, db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == user_credentials.email).first()
    if not user or not verify_password(
        user_credentials.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verify your email before logging in",
        )

    return {
        "access_token": create_access_token(user.email),
        "token_type": "bearer",
    }


@router.get("/verify-email", response_class=HTMLResponse)
def verify_email(token: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    import hashlib

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    user = db.query(User).filter(User.verification_token_hash == token_hash).first()
    expires_at = user.verification_expires_at if user else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if not user or not expires_at or expires_at <= datetime.now(timezone.utc):
        return HTMLResponse(
            "<h1>Verification link expired</h1>"
            "<p>Request a new verification email and try again.</p>",
            status_code=400,
        )

    user.is_email_verified = True
    user.verification_token_hash = None
    user.verification_expires_at = None
    db.commit()
    return HTMLResponse(
        "<h1>Email verified</h1>"
        '<p>Your account is ready. <a href="/login.html">Log in</a>.</p>'
    )


@router.get("/me", response_model=UserProfile)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/profile", response_model=UserProfile)
def update_profile(
    profile_update: DisplayPlayerIdChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.display_player_id = profile_update.display_player_id.strip()
    if not current_user.display_player_id:
        raise HTTPException(status_code=400, detail="Display Player ID cannot be empty")
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/change-password")
def change_password(
    password_change: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(password_change.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(password_change.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


@router.delete("/account")
def delete_account(
    request: AccountDelete,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(request.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Password is incorrect")

    user_tables = ("user_collections", "wildcard_inventories", "match_histories")
    existing_tables = set(inspect(db.bind).get_table_names())
    try:
        for table_name in user_tables:
            if table_name in existing_tables:
                db.execute(
                    text(f"DELETE FROM {table_name} WHERE user_id = :user_id"),
                    {"user_id": current_user.id},
                )
        db.delete(current_user)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Account cannot be deleted because related records remain",
        ) from error

    return {"message": "Account deleted successfully"}
