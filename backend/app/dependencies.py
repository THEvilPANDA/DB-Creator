from fastapi import Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from app.database import get_session
from app.models.user import User
from app.services.auth import decode_token


def get_arq(request: Request):
    """Return the Arq Redis pool from app state, or None if Redis is unavailable."""
    return getattr(request.app.state, "arq", None)


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    token = auth_header[7:]
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

    if payload.get("type") != "access":
        raise HTTPException(401, "Invalid token type")

    user = await session.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or inactive")
    return user


async def get_optional_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        return await get_current_user(request, session)
    except HTTPException:
        return None


async def require_admin(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    user = await get_current_user(request, session)
    if not user.is_admin:
        raise HTTPException(403, "Admin privileges required")
    return user
