from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import require_admin
from ..database import get_session
from ..models import (
    AssignmentStatus,
    AuditLog,
    Call,
    CallStatus,
    CallType,
    CmcAssignment,
    Property,
    TrainingStatus,
    User,
    UserRole,
)
from ..schemas import AdminDashboardOut, AssignCmcRequest, DashboardCountsOut, PropertyOut, ReassignCmcRequest, UserOut
from ..services.scheduling import SchedulingService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard", response_model=AdminDashboardOut)
async def admin_dashboard(
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminDashboardOut:
    properties = list((await session.execute(select(Property).order_by(Property.name))).scalars().all())
    cmcs = list((await session.execute(select(User).where(User.role == UserRole.cmc).order_by(User.full_name))).scalars().all())
    staff_count = await session.scalar(select(func.count(User.id)).where(User.role.in_([UserRole.staff, UserRole.owner]))) or 0
    open_first_calls = await session.scalar(
        select(func.count(CmcAssignment.id)).where(CmcAssignment.status == AssignmentStatus.active)
    ) or 0
    scheduled_calls = await session.scalar(select(func.count(Call.id)).where(Call.status == CallStatus.scheduled)) or 0
    return AdminDashboardOut(
        user=admin,
        counts=DashboardCountsOut(
            properties=len(properties),
            staff_users=staff_count,
            cmcs=len(cmcs),
            open_first_calls=open_first_calls,
            scheduled_calls=scheduled_calls,
        ),
        properties=properties,
        cmcs=cmcs,
    )


@router.get("/cmcs", response_model=list[UserOut])
async def list_cmcs(
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[User]:
    result = await session.execute(select(User).where(User.role == UserRole.cmc).order_by(User.full_name))
    return list(result.scalars().all())


@router.get("/properties", response_model=list[PropertyOut])
async def list_properties(
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[Property]:
    result = await session.execute(select(Property).order_by(Property.name))
    return list(result.scalars().all())


@router.post("/assign-cmc")
async def assign_cmc(
    payload: AssignCmcRequest,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    cmc = await session.get(User, payload.cmc_user_id)
    prop = await session.get(Property, payload.property_id)
    if not cmc or cmc.role != UserRole.cmc:
        raise HTTPException(status_code=404, detail="CMC not found")
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    active_result = await session.execute(
        select(CmcAssignment).where(
            CmcAssignment.property_id == payload.property_id,
            CmcAssignment.status == AssignmentStatus.active,
        )
    )
    for assignment in active_result.scalars().all():
        assignment.status = AssignmentStatus.inactive
        assignment.ended_at = datetime.now(timezone.utc)
        session.add(assignment)

    assignment = CmcAssignment(
        property_id=payload.property_id,
        cmc_user_id=payload.cmc_user_id,
        assigned_by_user_id=admin.id,
        status=AssignmentStatus.active,
        first_call_due_at=payload.first_call_due_at,
    )
    session.add(assignment)
    session.add(AuditLog(actor_user_id=admin.id, action="assign_cmc", entity_type="property", entity_id=payload.property_id, metadata_json=payload.model_dump(mode="json")))
    await session.commit()
    return {"assignment_id": assignment.id, "status": "assigned"}


@router.post("/reassign-cmc")
async def reassign_cmc(
    payload: ReassignCmcRequest,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    active_result = await session.execute(
        select(CmcAssignment)
        .options(selectinload(CmcAssignment.cmc_user))
        .where(CmcAssignment.property_id == payload.property_id, CmcAssignment.status == AssignmentStatus.active)
    )
    active = active_result.scalars().first()
    if not active:
        raise HTTPException(status_code=404, detail="Active assignment not found")
    old_cmc = active.cmc_user
    new_cmc = await session.get(User, payload.new_cmc_user_id)
    if not new_cmc or new_cmc.role != UserRole.cmc:
        raise HTTPException(status_code=404, detail="New CMC not found")

    active.status = AssignmentStatus.inactive
    active.ended_at = datetime.now(timezone.utc)
    session.add(active)

    new_assignment = CmcAssignment(
        property_id=payload.property_id,
        cmc_user_id=new_cmc.id,
        assigned_by_user_id=admin.id,
        status=AssignmentStatus.active,
        first_call_due_at=active.first_call_due_at,
    )
    session.add(new_assignment)
    transferred = 0
    if payload.transfer_future_calls:
        transferred = await SchedulingService().transfer_future_calls(session, payload.property_id, old_cmc, new_cmc)
    session.add(AuditLog(actor_user_id=admin.id, action="reassign_cmc", entity_type="property", entity_id=payload.property_id, metadata_json=payload.model_dump(mode="json")))
    await session.commit()
    return {"status": "reassigned", "new_assignment_id": new_assignment.id, "future_calls_transferred": transferred}
