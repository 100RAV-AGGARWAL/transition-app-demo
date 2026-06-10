from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    AssignmentStatus,
    CmcAssignment,
    Property,
    PropertyStaff,
    TrainingStatus,
    TransitionStatus,
    User,
    UserRole,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
CMC_ID = "00000000-0000-0000-0000-000000000002"
CMC_ADMIN_ID = "00000000-0000-0000-0000-000000000003"
OWNER_ID = "00000000-0000-0000-0000-000000000004"
STAFF_ID = "00000000-0000-0000-0000-000000000005"
STAFF_2_ID = "00000000-0000-0000-0000-000000000006"
PROPERTY_ID = "10000000-0000-0000-0000-000000000001"


async def seed_if_empty(session: AsyncSession) -> None:
    result = await session.execute(select(User).limit(1))
    if result.scalars().first():
        return

    users = [
        User(id=ADMIN_ID, email="admin@example.com", full_name="Avery Admin", role=UserRole.admin, is_admin=True),
        User(id=CMC_ID, email="cmc@example.com", full_name="Casey CMC", role=UserRole.cmc, zoom_user_id="cmc@example.com", microsoft_user_id="cmc@example.com"),
        User(id=CMC_ADMIN_ID, email="cmc.admin@example.com", full_name="Morgan CMC Admin", role=UserRole.cmc, is_admin=True, zoom_user_id="cmc.admin@example.com", microsoft_user_id="cmc.admin@example.com"),
        User(id=OWNER_ID, email="owner@example.com", full_name="Olivia Owner", role=UserRole.owner),
        User(id=STAFF_ID, email="staff@example.com", full_name="Sam Staff", role=UserRole.staff),
        User(id=STAFF_2_ID, email="staff2@example.com", full_name="Taylor Trainer", role=UserRole.staff),
    ]
    session.add_all(users)

    property_row = Property(
        id=PROPERTY_ID,
        name="Sunrise Apartments",
        address="120 Migration Lane, Pune, MH",
        old_tool_property_id="OLD-APT-120",
        new_tool_property_id="NEW-APT-120",
        transition_status=TransitionStatus.first_call_pending,
        owner_user_id=OWNER_ID,
    )
    session.add(property_row)

    session.add_all([
        PropertyStaff(property_id=PROPERTY_ID, user_id=OWNER_ID, title="Property Owner", is_primary_contact=True),
        PropertyStaff(property_id=PROPERTY_ID, user_id=STAFF_ID, title="Leasing Manager", is_primary_contact=True),
        PropertyStaff(property_id=PROPERTY_ID, user_id=STAFF_2_ID, title="Front Desk Associate", is_primary_contact=False),
    ])

    session.add(CmcAssignment(
        property_id=PROPERTY_ID,
        cmc_user_id=CMC_ID,
        assigned_by_user_id=ADMIN_ID,
        status=AssignmentStatus.active,
        first_call_due_at=datetime.now(timezone.utc) + timedelta(days=2),
    ))

    session.add_all([
        TrainingStatus(property_id=PROPERTY_ID, user_id=OWNER_ID, status="complete", progress_percent=100, required_modules=6, completed_modules=6, last_synced_at=datetime.now(timezone.utc)),
        TrainingStatus(property_id=PROPERTY_ID, user_id=STAFF_ID, status="in_progress", progress_percent=67, required_modules=6, completed_modules=4, last_synced_at=datetime.now(timezone.utc)),
        TrainingStatus(property_id=PROPERTY_ID, user_id=STAFF_2_ID, status="not_started", progress_percent=0, required_modules=6, completed_modules=0, last_synced_at=datetime.now(timezone.utc)),
    ])
    await session.commit()
