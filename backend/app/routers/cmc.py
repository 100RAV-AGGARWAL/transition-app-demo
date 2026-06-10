from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import require_cmc_or_admin
from ..database import get_session
from ..models import AssignmentStatus, Call, CallStatus, CallType, CmcAssignment, User
from ..schemas import AssignmentOut

router = APIRouter(prefix="/cmc", tags=["cmc"])


@router.get("/assignments", response_model=list[AssignmentOut])
async def my_assignments(
    user: User = Depends(require_cmc_or_admin),
    session: AsyncSession = Depends(get_session),
) -> list[AssignmentOut]:
    result = await session.execute(
        select(CmcAssignment)
        .options(selectinload(CmcAssignment.property), selectinload(CmcAssignment.cmc_user))
        .where(CmcAssignment.cmc_user_id == user.id, CmcAssignment.status == AssignmentStatus.active)
        .order_by(CmcAssignment.assigned_at.desc())
    )
    assignments = list(result.scalars().all())
    response: list[AssignmentOut] = []
    for assignment in assignments:
        first_call = await session.execute(
            select(Call).where(
                Call.property_id == assignment.property_id,
                Call.call_type == CallType.first_call,
                Call.status.in_([CallStatus.scheduled, CallStatus.completed]),
            )
        )
        call_row = first_call.scalars().first()
        status = call_row.status.value if call_row else "not_scheduled"
        response.append(
            AssignmentOut(
                id=assignment.id,
                property=assignment.property,
                cmc=assignment.cmc_user,
                assigned_at=assignment.assigned_at,
                first_call_due_at=assignment.first_call_due_at,
                first_call_status=status,
            )
        )
    return response
