from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime
import httpx

from ..settings import get_settings


@dataclass
class ZoomMeeting:
    meeting_id: str
    join_url: str
    start_url: str | None = None


class ZoomClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def _token(self) -> str:
        if not all([self.settings.zoom_client_id, self.settings.zoom_client_secret, self.settings.zoom_account_id]):
            raise RuntimeError("Zoom credentials are not configured")
        basic = base64.b64encode(
            f"{self.settings.zoom_client_id}:{self.settings.zoom_client_secret}".encode("utf-8")
        ).decode("utf-8")
        url = "https://zoom.us/oauth/token"
        params = {"grant_type": "account_credentials", "account_id": self.settings.zoom_account_id}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, params=params, headers={"Authorization": f"Basic {basic}"})
            response.raise_for_status()
            return response.json()["access_token"]

    async def create_meeting(
        self,
        host_zoom_user_id: str,
        topic: str,
        start_time: datetime,
        duration_minutes: int,
        timezone: str,
        agenda: str,
    ) -> ZoomMeeting:
        if self.settings.mock_integrations:
            meeting_id = f"mock-zoom-{uuid.uuid4().hex[:10]}"
            return ZoomMeeting(
                meeting_id=meeting_id,
                join_url=f"https://zoom.example.test/j/{meeting_id}",
                start_url=f"https://zoom.example.test/s/{meeting_id}",
            )

        token = await self._token()
        payload = {
            "topic": topic,
            "type": 2,
            "start_time": start_time.isoformat(),
            "duration": duration_minutes,
            "timezone": timezone,
            "agenda": agenda,
            "settings": {
                "join_before_host": False,
                "waiting_room": True,
                "approval_type": 2,
                "calendar_type": 2,
            },
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"https://api.zoom.us/v2/users/{host_zoom_user_id}/meetings",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()
            return ZoomMeeting(
                meeting_id=str(data.get("id")),
                join_url=data["join_url"],
                start_url=data.get("start_url"),
            )

    async def delete_meeting(self, meeting_id: str) -> None:
        if self.settings.mock_integrations or meeting_id.startswith("mock-"):
            return
        token = await self._token()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.delete(
                f"https://api.zoom.us/v2/meetings/{meeting_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code not in (204, 404):
                response.raise_for_status()
