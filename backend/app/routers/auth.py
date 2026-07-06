from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..database import get_db
from ..models import User
from ..rate_limit import login_limiter, register_limiter
from ..schemas import Token, UserCreate, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=Token, status_code=201)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)):
    if not register_limiter.allow(_client_key(request)):
        raise HTTPException(429, "Too many registration attempts. Try again later.")
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=payload.email, password_hash=hash_password(payload.password),
                business_name=payload.business_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return Token(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    if not login_limiter.allow(_client_key(request)):
        raise HTTPException(429, "Too many login attempts. Try again later.")
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return Token(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
