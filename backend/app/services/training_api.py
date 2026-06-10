from __future__ import annotations

from datetime import datetime, timezone
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PropertyStaff, TrainingStatus
from ..settings import get_settings


class TrainingClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def sync_property_training(self, session: AsyncSession, property_id: str) -> list[TrainingStatus]:
        """Synchronize training data from a third-party provider.

        In mock mode this returns locally seeded records. In production, map the provider's
        user/property identifiers to local IDs, upsert TrainingStatus rows, and store the raw payload.
        """
        if self.settings.mock_integrations or not self.settings.training_api_base_url:
            result = await session.execute(
                select(TrainingStatus).where(TrainingStatus.property_id == property_id)
            )
            return list(result.scalars().all())

        headers = {"Authorization": f"Bearer {self.settings.training_api_key}"} if self.settings.training_api_key else {}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.settings.training_api_base_url.rstrip('/')}/properties/{property_id}/training-status",
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()

        existing_result = await session.execute(select(TrainingStatus).where(TrainingStatus.property_id == property_id))
        existing = {row.user_id: row for row in existing_result.scalars().all()}
        staff_result = await session.execute(select(PropertyStaff).where(PropertyStaff.property_id == property_id))
        staff_ids = {membership.user_id for membership in staff_result.scalars().all()}

        rows: list[TrainingStatus] = []
        for item in payload.get("staff", []):
            user_id = item.get("user_id")
            if user_id not in staff_ids:
                continue
            row = existing.get(user_id) or TrainingStatus(property_id=property_id, user_id=user_id)
            row.external_training_id = item.get("training_id")
            row.status = item.get("status", "unknown")
            row.progress_percent = int(item.get("progress_percent", 0))
            row.required_modules = int(item.get("required_modules", 0))
            row.completed_modules = int(item.get("completed_modules", 0))
            row.last_synced_at = datetime.now(timezone.utc)
            row.raw_payload = item
            session.add(row)
            rows.append(row)
        await session.flush()
        return rows
