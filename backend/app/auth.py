from fastapi import Depends, Header, HTTPException, Query, status
from jwt import PyJWKClient, InvalidTokenError, decode as jwt_decode
from urllib.parse import urljoin
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_session
from .models import User, UserRole
from .settings import get_settings


async def get_current_user(
        x_user_id: str | None = Header(default=None, alias="X-User-Id"),
        user_id: str | None = Query(default=None, alias="user_id"),
        session: AsyncSession = Depends(get_session),
        authorization: str | None = Header(default=None, alias="Authorization"),
) -> User:
    settings = get_settings()

    if settings.dev_auth_enabled:
        if not x_user_id:
            x_user_id = user_id
        if not x_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Missing X-User-Id header or user_id query param. Use /api/debug/seed-users to discover POC users."
                ),
            )

        user = await session.get(User, x_user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive user")
        return user

    # Production: validate Authorization Bearer token using Okta (or any OIDC provider)
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header")
    token = parts[1]

    issuer = settings.okta_issuer
    audience = settings.okta_client_id
    if not issuer or not audience:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Identity provider not configured")

    # Use PyJWKClient to fetch signing key from JWKS endpoint
    try:
        jwks_url = urljoin(issuer if issuer.endswith('/') else issuer + '/', 'v1/keys')
        jwk_client = PyJWKClient(jwks_url)
        signing_key = jwk_client.get_signing_key_from_jwt(token)
        payload = jwt_decode(token, signing_key.key, algorithms=["RS256"], audience=audience, issuer=issuer.rstrip('/'))
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token validation failed: {exc}")

    # Map token claims to user record in DB (by email)
    user_email = payload.get('email') or payload.get('preferred_username') or payload.get('sub')
    if not user_email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing email claim")

    # Attempt to find user by email
    result = await session.execute(select(User).where(User.email == user_email))
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive user")
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
