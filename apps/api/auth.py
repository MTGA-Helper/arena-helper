import traceback
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import JWTError, jwt

from apps.api.database import get_db, engine, Base
from apps.api.models import User
from apps.api.schemas import UserCreate, UserLogin, Token

try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Table creation warning: {e}")

# Clean router with NO prefix here
router = APIRouter(tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# FIX (Oct 21, 2026, audit AU-1): was a hardcoded placeholder string in a
# public repo - anyone could forge JWTs for any account. Now read from the
# environment and fail fast: a missing or placeholder secret stops the boot.
import os
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY == "super-secret-key-change-me":
    raise RuntimeError("SECRET_KEY env var must be set to a real secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/register", status_code=201)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    try:
        # FIX (Oct 21, 2026, audit AU-1): removed the registration diagnostics
        # block - it printed the DB bind URL (credentials embedded) to stdout
        # on every signup, leaking the connection string into server logs.
        db_user = db.query(User).filter(User.email == user.email).first()
        if db_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        hashed_password = get_password_hash(user.password)
        new_user = User(email=user.email, hashed_password=hashed_password)
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return {"message": "User created successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        # FIX (Oct 21, 2026, audit AU-1): traceback print to stdout removed (log hygiene).
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/login", response_model=Token)
def login_for_access_token(user_credentials: UserLogin, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.email == user_credentials.email).first()
        if not user or not verify_password(user_credentials.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token = create_access_token(data={"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        # FIX (Oct 21, 2026, audit AU-1): exception print to stdout removed (log hygiene).
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")




