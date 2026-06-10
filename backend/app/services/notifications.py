from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Call, Notification, NotificationStatus


class NotificationService:
    """POC notification service.

    Production options:
    - Amazon SES for transactional email.
    - Amazon SNS/Pinpoint for SMS if SMS reminders are required.
    - Celery, EventBridge Scheduler, or APScheduler for reminder dispatch.
    """

    async def queue_call_notifications(
        self,
        session: AsyncSession,
        call: Call,
        recipient_emails: list[str],
    ) -> list[Notification]:
        notifications: list[Notification] = []
        reminder_times = [
            ("confirmation", datetime.now(timezone.utc)),
            ("reminder_24h", call.start_time - timedelta(hours=24)),
            ("reminder_1h", call.start_time - timedelta(hours=1)),
        ]
        for email in sorted(set(recipient_emails)):
            for notification_type, scheduled_for in reminder_times:
                row = Notification(
                    call_id=call.id,
                    recipient_email=email,
                    notification_type=notification_type,
                    scheduled_for=scheduled_for,
                    status=NotificationStatus.queued,
                )
                session.add(row)
                notifications.append(row)
        await session.flush()
        return notifications

    async def mark_sent(self, session: AsyncSession, notification: Notification) -> None:
        notification.status = NotificationStatus.sent
        notification.sent_at = datetime.now(timezone.utc)
        session.add(notification)
