"""Auth router — registration and login with rate limiting."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import Token, UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])

limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Create a new user account and return a JWT."""
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    user = User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=token)


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(
    request: Request,
    payload: UserCreate,
    db: Session = Depends(get_db),
):
    """Authenticate and return a JWT. Rate-limited to 10 requests/minute per IP."""
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=token)


@router.post("/api-key", response_model=Token)
def generate_api_key(tenant_id: int = Depends(decode_token)):
    """Generate a long-lived API Key (10 years) for server-to-server integration."""
    expires = timedelta(days=3650)
    token = create_access_token(data={"sub": str(tenant_id)}, expires_delta=expires)
    return Token(access_token=token)
