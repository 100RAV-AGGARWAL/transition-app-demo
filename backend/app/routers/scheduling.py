from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_session
from ..models import AssignmentStatus, Call, CallStatus, CallType, CmcAssignment, Property, PropertyStaff, User, UserRole
from ..schemas import BookCallRequest, CallOut, RescheduleCallRequest, SlotOut
from ..services.scheduling import SchedulingService

router = APIRouter(prefix="/scheduling", tags=["scheduling"])


@router.get("/slots", response_model=list[SlotOut])
async def available_slots(
        property_id: str,
        start: datetime = Query(...,
                                description="ISO timestamp with timezone"),
        end: datetime = Query(..., description="ISO timestamp with timezone"),
        timezone: str = "Asia/Kolkata",
        duration_minutes: int = 30,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
) -> list[SlotOut]:
    await _assert_can_access_property(session, user, property_id)
    assignment = await SchedulingService().active_assignment(
        session, property_id)
    cmc = await session.get(User, assignment.cmc_user_id)
    return await SchedulingService().get_available_slots(
        session, cmc, start, end, timezone, duration_minutes)


@router.post("/book", response_model=CallOut)
async def book_call(
        payload: BookCallRequest,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
) -> Call:
    await _assert_can_access_property(session, user, payload.property_id)
    service = SchedulingService()
    call = await service.book_call(
        session=session,
        property_id=payload.property_id,
        scheduled_by=user,
        call_type=payload.call_type,
        start=payload.start_time,
        end=payload.end_time,
        timezone=payload.timezone,
        attendee_user_ids=payload.attendee_user_ids,
    )
    await session.commit()
    await session.refresh(call)
    return call


@router.post("/{call_id}/accept", response_model=CallOut)
async def accept_call(
        call_id: str,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
) -> Call:
    result = await session.execute(select(Call).where(Call.id == call_id))
    call = result.scalars().first()
    if not call:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Call not found")
    service = SchedulingService()
    call = await service.accept_follow_up_request(session, call, user)
    await session.commit()
    await session.refresh(call)
    return call


@router.post("/{call_id}/reschedule", response_model=CallOut)
async def reschedule_call(
        call_id: str,
        payload: RescheduleCallRequest,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
) -> Call:
    result = await session.execute(select(Call).where(Call.id == call_id))
    call = result.scalars().first()
    if not call:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Call not found")
    await _assert_can_access_property(session, user, call.property_id)
    service = SchedulingService()
    call = await service.reschedule_call(session, call, payload.start_time,
                                         payload.end_time, payload.timezone)
    await session.commit()
    await session.refresh(call)
    return call


@router.post("/{call_id}/missed", response_model=CallOut)
async def missed_call(
        call_id: str,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
) -> Call:
    result = await session.execute(select(Call).where(Call.id == call_id))
    call = result.scalars().first()
    if not call:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Call not found")
    await _assert_can_access_property(session, user, call.property_id)
    service = SchedulingService()
    call = await service.mark_call_missed(session, call)
    await session.commit()
    await session.refresh(call)
    return call


@router.delete("/{call_id}")
async def delete_call(
        call_id: str,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    result = await session.execute(select(Call).where(Call.id == call_id))
    call = result.scalars().first()
    if not call:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Call not found")
    await _assert_can_access_property(session, user, call.property_id)
    service = SchedulingService()
    await service.delete_call(session, call)
    await session.commit()
    return {"status": "deleted"}


@router.get("/calls", response_model=list[CallOut])
async def my_calls(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
) -> list[Call]:
    if user.is_admin or user.role == UserRole.admin:
        result = await session.execute(
            select(Call).order_by(Call.start_time.desc()))
    elif user.role == UserRole.cmc:
        result = await session.execute(
            select(Call).where(Call.cmc_user_id == user.id).order_by(
                Call.start_time.desc()))
    else:
        result = await session.execute(
            select(Call).join(Property, Call.property_id == Property.id).where(
                or_(
                    Property.owner_user_id == user.id,
                    Property.id.in_(
                        select(PropertyStaff.property_id).where(
                            PropertyStaff.user_id == user.id)),
                )).order_by(Call.start_time.desc()))
    return list(result.scalars().all())


async def _assert_can_access_property(session: AsyncSession, user: User,
                                      property_id: str) -> None:
    if user.is_admin or user.role == UserRole.admin:
        return
    if user.role == UserRole.cmc:
        result = await session.execute(
            select(CmcAssignment.id).where(
                CmcAssignment.property_id == property_id,
                CmcAssignment.cmc_user_id == user.id,
                CmcAssignment.status == AssignmentStatus.active,
            ))
    else:
        result = await session.execute(
            select(PropertyStaff.id).where(
                PropertyStaff.property_id == property_id,
                PropertyStaff.user_id == user.id))
    if not result.first():
        from fastapi import HTTPException
        raise HTTPException(status_code=403,
                            detail="No access to this property")
