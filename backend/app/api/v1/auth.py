from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt

from app.database import get_session
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import UserCreate, UserLogin, TokenRefresh, TokenResponse, UserRead
from app.services.auth import hash_password, verify_password, create_access_token, create_refresh_token, decode_token

router = APIRouter(prefix="/auth", tags=["auth"])

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    _limiter = Limiter(key_func=get_remote_address)
    _rate_limit = _limiter.limit("10/minute")
except ImportError:
    def _rate_limit(fn):  # type: ignore[misc]
        return fn


@router.post("/register", response_model=UserRead, status_code=201)
async def register(body: UserCreate, session: AsyncSession = Depends(get_session)):
    existing = await session.execute(
        select(User).where(User.username == body.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Username already taken")

    email_exists = await session.execute(
        select(User).where(User.email == body.email)
    )
    if email_exists.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
@_rate_limit
async def login(request: Request, body: UserLogin, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(User).where(User.username == body.username, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")

    return TokenResponse(
        access_token=create_access_token(user.id, user.username, user.is_admin),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: TokenRefresh, session: AsyncSession = Depends(get_session)):
    try:
        payload = decode_token(body.refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid token type")

    user = await session.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or inactive")

    return TokenResponse(
        access_token=create_access_token(user.id, user.username, user.is_admin),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)):
    return user
