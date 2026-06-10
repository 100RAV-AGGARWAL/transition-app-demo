from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import User
from ..schemas import UserOut

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/seed-users", response_model=list[UserOut])
async def seed_users(session: AsyncSession = Depends(get_session)) -> list[User]:
    result = await session.execute(select(User).order_by(User.role, User.email))
    return list(result.scalars().all())
