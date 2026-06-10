from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import uuid
import httpx

from ..settings import get_settings


@dataclass(frozen=True)
class BusyInterval:
    start_time: datetime
    end_time: datetime


@dataclass(frozen=True)
class CalendarEvent:
    event_id: str
    web_link: str | None = None


class MicrosoftGraphClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def _token(self) -> str:
        if not all([
            self.settings.microsoft_tenant_id,
            self.settings.microsoft_client_id,
            self.settings.microsoft_client_secret,
        ]):
            raise RuntimeError("Microsoft Graph credentials are not configured")
        url = f"https://login.microsoftonline.com/{self.settings.microsoft_tenant_id}/oauth2/v2.0/token"
        form = {
            "client_id": self.settings.microsoft_client_id,
            "client_secret": self.settings.microsoft_client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, data=form)
            response.raise_for_status()
            return response.json()["access_token"]

    async def get_busy_intervals(
        self,
        cmc_email_or_id: str,
        start: datetime,
        end: datetime,
        timezone: str,
    ) -> list[BusyInterval]:
        if self.settings.mock_integrations:
            # Demo busy blocks. Production reads actual Outlook calendar free/busy data.
            day_anchor = start.replace(hour=0, minute=0, second=0, microsecond=0)
            return [
                BusyInterval(day_anchor.replace(hour=10, minute=0), day_anchor.replace(hour=10, minute=30)),
                BusyInterval(day_anchor.replace(hour=13, minute=0), day_anchor.replace(hour=14, minute=0)),
            ]

        token = await self._token()
        payload = {
            "schedules": [cmc_email_or_id],
            "startTime": {"dateTime": start.replace(tzinfo=None).isoformat(), "timeZone": timezone},
            "endTime": {"dateTime": end.replace(tzinfo=None).isoformat(), "timeZone": timezone},
            "availabilityViewInterval": self.settings.slot_interval_minutes,
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": f'outlook.timezone="{timezone}"',
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"https://graph.microsoft.com/v1.0/users/{cmc_email_or_id}/calendar/getSchedule",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        intervals: list[BusyInterval] = []
        for schedule in data.get("value", []):
            for item in schedule.get("scheduleItems", []):
                status = item.get("status")
                if status in {"busy", "tentative", "oof", "workingElsewhere"}:
                    intervals.append(
                        BusyInterval(
                            datetime.fromisoformat(item["start"]["dateTime"]),
                            datetime.fromisoformat(item["end"]["dateTime"]),
                        )
                    )
        return intervals

    async def create_calendar_event(
        self,
        organizer_email_or_id: str,
        subject: str,
        body_html: str,
        start: datetime,
        end: datetime,
        timezone: str,
        attendee_emails: list[str],
        transaction_id: str | None = None,
    ) -> CalendarEvent:
        if self.settings.mock_integrations:
            event_id = f"mock-outlook-{uuid.uuid4().hex[:10]}"
            return CalendarEvent(event_id=event_id, web_link=f"https://outlook.example.test/events/{event_id}")

        token = await self._token()
        payload = {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body_html},
            "start": {"dateTime": start.replace(tzinfo=None).isoformat(), "timeZone": timezone},
            "end": {"dateTime": end.replace(tzinfo=None).isoformat(), "timeZone": timezone},
            "attendees": [
                {"emailAddress": {"address": email}, "type": "required"}
                for email in attendee_emails
            ],
            "allowNewTimeProposals": False,
            "transactionId": transaction_id or str(uuid.uuid4()),
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": f'outlook.timezone="{timezone}"',
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"https://graph.microsoft.com/v1.0/users/{organizer_email_or_id}/events",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return CalendarEvent(event_id=data["id"], web_link=data.get("webLink"))

    async def delete_calendar_event(self, organizer_email_or_id: str, event_id: str) -> None:
        if self.settings.mock_integrations or event_id.startswith("mock-"):
            return
        token = await self._token()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.delete(
                f"https://graph.microsoft.com/v1.0/users/{organizer_email_or_id}/events/{event_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code not in (204, 404):
                response.raise_for_status()
