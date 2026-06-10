from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_session
from .models import User, UserRole
from .settings import get_settings


async def get_current_user(
        x_user_id: str | None = Header(default=None, alias="X-User-Id"),
        user_id: str | None = Query(default=None, alias="user_id"),
        session: AsyncSession = Depends(get_session),
) -> User:
    settings = get_settings()
    if not settings.dev_auth_enabled:
        # Production placeholder: validate JWT from Cognito/Entra/Okta/Auth0 and map claims to user.
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED,
                            detail="Production auth not configured")

    if not x_user_id:
        x_user_id = user_id
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=
            "Missing X-User-Id header or user_id query param. Use /api/debug/seed-users to discover POC users.",
        )

    user = await session.get(User, x_user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or inactive user")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin and user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Admin access required")
    return user


def require_cmc_or_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.cmc and not user.is_admin and user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="CMC or admin access required")
    return user
