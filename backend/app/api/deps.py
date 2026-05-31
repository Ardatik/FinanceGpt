from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_session
from app.models import User


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization required")
    try:
        payload = decode_token(credentials.credentials)
        user_id = UUID(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_user_from_ws_token(token: str, session: AsyncSession) -> User | None:
    try:
        payload = decode_token(token)
        user_id = UUID(payload["sub"])
    except Exception:
        return None
    return await session.get(User, user_id)


async def require_cushion_token(
    x_cushion_token: str | None = Header(default=None),
    current_user: User = Depends(get_current_user),
) -> User:
    if not x_cushion_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cushion unlock required")
    try:
        payload = decode_token(x_cushion_token, expected_type="cushion")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid cushion token") from exc
    if payload.get("sub") != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid cushion token")
    return current_user


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()
