from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import get_current_user
from ..database import get_session
from ..models import AssignmentStatus, CmcAssignment, Property, PropertyStaff, TrainingStatus, User, UserRole
from ..schemas import PropertyOut, StaffTrainingOut
from ..services.training_api import TrainingClient

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("", response_model=list[PropertyOut])
async def list_my_properties(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Property]:
    if user.role == UserRole.admin or user.is_admin:
        result = await session.execute(select(Property).order_by(Property.name))
    elif user.role == UserRole.owner:
        result = await session.execute(select(Property).where(Property.owner_user_id == user.id).order_by(Property.name))
    elif user.role == UserRole.cmc:
        result = await session.execute(
            select(Property).join(Property.assignments).where(Property.assignments.any(cmc_user_id=user.id))
        )
    else:
        result = await session.execute(
            select(Property).join(PropertyStaff, PropertyStaff.property_id == Property.id).where(PropertyStaff.user_id == user.id)
        )
    return list(result.scalars().unique().all())


@router.get("/{property_id}/training", response_model=list[StaffTrainingOut])
async def property_training(
    property_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[StaffTrainingOut]:
    await _assert_property_access(session, user, property_id)
    await TrainingClient().sync_property_training(session, property_id)
    await session.commit()

    memberships_result = await session.execute(
        select(PropertyStaff)
        .options(selectinload(PropertyStaff.user))
        .where(PropertyStaff.property_id == property_id)
    )
    memberships = list(memberships_result.scalars().all())
    training_result = await session.execute(select(TrainingStatus).where(TrainingStatus.property_id == property_id))
    training_by_user = {row.user_id: row for row in training_result.scalars().all()}

    if user.role == UserRole.staff and not user.is_admin:
        memberships = [membership for membership in memberships if membership.user_id == user.id]

    return [
        StaffTrainingOut(
            user=membership.user,
            training=training_by_user.get(membership.user_id),
            title=membership.title,
            is_primary_contact=membership.is_primary_contact,
        )
        for membership in memberships
    ]


async def _assert_property_access(session: AsyncSession, user: User, property_id: str) -> None:
    if user.is_admin or user.role == UserRole.admin:
        return
    if user.role == UserRole.owner:
        result = await session.execute(select(Property.id).where(Property.id == property_id, Property.owner_user_id == user.id))
    elif user.role == UserRole.cmc:
        result = await session.execute(select(Property.id).join(Property.assignments).where(Property.id == property_id))
    else:
        result = await session.execute(
            select(PropertyStaff.id).where(PropertyStaff.property_id == property_id, PropertyStaff.user_id == user.id)
        )
    if not result.first():
        raise HTTPException(status_code=403, detail="No access to this property")
