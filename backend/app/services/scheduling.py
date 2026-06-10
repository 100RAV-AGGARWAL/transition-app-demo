from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Call, CallStatus, CallType, CmcAssignment, AssignmentStatus, Notification, PropertyStaff, User, UserRole
from ..schemas import SlotOut
from ..settings import get_settings
from .microsoft_graph import BusyInterval, MicrosoftGraphClient
from .notifications import NotificationService
from .zoom import ZoomClient


class SchedulingService:

    def __init__(self) -> None:
        self.settings = get_settings()
        self.graph = MicrosoftGraphClient()
        self.zoom = ZoomClient()
        self.notifications = NotificationService()

    async def active_assignment(self, session: AsyncSession,
                                property_id: str) -> CmcAssignment:
        result = await session.execute(
            select(CmcAssignment).where(
                CmcAssignment.property_id == property_id,
                CmcAssignment.status == AssignmentStatus.active,
            ))
        assignment = result.scalars().first()
        if not assignment:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="No active CMC assignment for property")
        return assignment

    async def get_available_slots(
        self,
        session: AsyncSession,
        cmc: User,
        start: datetime,
        end: datetime,
        timezone: str,
        duration_minutes: int | None = None,
        exclude_call_id: str | None = None,
    ) -> list[SlotOut]:
        duration = duration_minutes or self.settings.default_call_duration_minutes
        tz = ZoneInfo(timezone)
        start_local = start.astimezone(tz) if start.tzinfo else start.replace(
            tzinfo=tz)
        end_local = end.astimezone(tz) if end.tzinfo else end.replace(
            tzinfo=tz)

        busy = await self.graph.get_busy_intervals(cmc.email, start_local,
                                                   end_local, timezone)
        busy.extend(await self._local_busy_intervals(
            session,
            cmc.id,
            start_local,
            end_local,
            exclude_call_id=exclude_call_id))
        busy = self._merge_intervals(busy)

        slots: list[SlotOut] = []
        current_day = start_local.date()
        while datetime.combine(current_day, datetime.min.time(),
                               tzinfo=tz) < end_local:
            day_start = datetime.combine(
                current_day, datetime.min.time(), tzinfo=tz).replace(
                    hour=self.settings.business_day_start_hour,
                    minute=0,
                )
            day_end = datetime.combine(
                current_day, datetime.min.time(), tzinfo=tz).replace(
                    hour=self.settings.business_day_end_hour,
                    minute=0,
                )
            cursor = max(
                day_start,
                self._round_up(start_local,
                               self.settings.slot_interval_minutes))
            while cursor + timedelta(minutes=duration) <= min(
                    day_end, end_local):
                candidate_end = cursor + timedelta(minutes=duration)
                if cursor >= start_local and not self._overlaps_any(
                        cursor, candidate_end, busy):
                    slots.append(
                        SlotOut(start_time=cursor,
                                end_time=candidate_end,
                                timezone=timezone))
                cursor += timedelta(
                    minutes=self.settings.slot_interval_minutes)
            current_day = current_day + timedelta(days=1)
        return slots

    async def book_call(
        self,
        session: AsyncSession,
        property_id: str,
        scheduled_by: User,
        call_type: CallType,
        start: datetime,
        end: datetime,
        timezone: str,
        attendee_user_ids: list[str],
    ) -> Call:
        assignment = await self.active_assignment(session, property_id)
        cmc = await session.get(User, assignment.cmc_user_id)
        if not cmc:
            raise HTTPException(status_code=404,
                                detail="Assigned CMC user not found")

        if call_type == CallType.first_call and scheduled_by.role != UserRole.cmc and not scheduled_by.is_admin:
            raise HTTPException(
                status_code=403,
                detail="Only CMC/admin can schedule the mandatory first call")
        if call_type == CallType.follow_up and not await self._first_call_exists(
                session, property_id):
            raise HTTPException(
                status_code=409,
                detail=
                "Follow-up calls are allowed only after the first call is scheduled"
            )

        duration = int((end - start).total_seconds() / 60)
        slots = await self.get_available_slots(session, cmc, start, end,
                                               timezone, duration)
        if not any(slot.start_time == start and slot.end_time == end
                   for slot in slots):
            raise HTTPException(status_code=409,
                                detail="Selected slot is no longer available")

        is_follow_up_request = (call_type == CallType.follow_up
                                and scheduled_by.role != UserRole.cmc
                                and not scheduled_by.is_admin)
        status = CallStatus.pending if is_follow_up_request else CallStatus.scheduled

        attendee_emails = await self._attendee_emails(session, property_id,
                                                      attendee_user_ids)
        zoom_meeting = None
        event = None
        topic = "Transition first call" if call_type == CallType.first_call else "Transition follow-up call"

        if status == CallStatus.scheduled:
            zoom_meeting = await self.zoom.create_meeting(
                host_zoom_user_id=cmc.zoom_user_id or cmc.email,
                topic=topic,
                start_time=start,
                duration_minutes=duration,
                timezone=timezone,
                agenda=f"{topic} for property {property_id}",
            )
            body_html = (
                f"<p>{topic}</p>"
                f"<p>Zoom link: <a href='{zoom_meeting.join_url}'>{zoom_meeting.join_url}</a></p>"
                "<p>Please join on time and have migration questions ready.</p>"
            )
            event = await self.graph.create_calendar_event(
                organizer_email_or_id=cmc.microsoft_user_id or cmc.email,
                subject=topic,
                body_html=body_html,
                start=start,
                end=end,
                timezone=timezone,
                attendee_emails=attendee_emails,
            )

        call = Call(
            property_id=property_id,
            cmc_user_id=cmc.id,
            scheduled_by_user_id=scheduled_by.id,
            call_type=call_type,
            status=status,
            start_time=start,
            end_time=end,
            timezone=timezone,
            zoom_meeting_id=zoom_meeting.meeting_id if zoom_meeting else None,
            zoom_join_url=zoom_meeting.join_url if zoom_meeting else None,
            zoom_start_url=zoom_meeting.start_url if zoom_meeting else None,
            outlook_event_id=event.event_id if event else None,
        )
        session.add(call)
        await session.flush()

        if status == CallStatus.scheduled:
            await self.notifications.queue_call_notifications(
                session, call, attendee_emails + [cmc.email])

        return call

    async def accept_follow_up_request(
        self,
        session: AsyncSession,
        call: Call,
        approver: User,
    ) -> Call:
        if call.call_type != CallType.follow_up or call.status != CallStatus.pending:
            raise HTTPException(
                status_code=409,
                detail="Only pending follow-up calls can be accepted")
        if approver.role != UserRole.cmc and not approver.is_admin:
            raise HTTPException(
                status_code=403,
                detail=
                "Only the assigned CMC or admin can accept follow-up requests")
        if approver.role == UserRole.cmc and call.cmc_user_id != approver.id:
            raise HTTPException(
                status_code=403,
                detail="Only the assigned CMC can accept this request")

        cmc = await session.get(User, call.cmc_user_id)
        if not cmc:
            raise HTTPException(status_code=404,
                                detail="Assigned CMC user not found")

        duration = int((call.end_time - call.start_time).total_seconds() / 60)
        slots = await self.get_available_slots(
            session,
            cmc,
            call.start_time,
            call.end_time,
            call.timezone,
            duration,
            exclude_call_id=call.id,
        )
        if not any(slot.start_time == call.start_time
                   and slot.end_time == call.end_time for slot in slots):
            raise HTTPException(status_code=409,
                                detail="Requested slot is no longer available")

        attendee_emails = await self._attendee_emails(session,
                                                      call.property_id, [])
        topic = "Transition follow-up call"
        zoom_meeting = await self.zoom.create_meeting(
            host_zoom_user_id=cmc.zoom_user_id or cmc.email,
            topic=topic,
            start_time=call.start_time,
            duration_minutes=duration,
            timezone=call.timezone,
            agenda=f"{topic} for property {call.property_id}",
        )
        body_html = (
            f"<p>{topic}</p>"
            f"<p>Zoom link: <a href='{zoom_meeting.join_url}'>{zoom_meeting.join_url}</a></p>"
            "<p>Please join on time and have migration questions ready.</p>")
        event = await self.graph.create_calendar_event(
            organizer_email_or_id=cmc.microsoft_user_id or cmc.email,
            subject=topic,
            body_html=body_html,
            start=call.start_time,
            end=call.end_time,
            timezone=call.timezone,
            attendee_emails=attendee_emails,
        )

        call.status = CallStatus.scheduled
        call.zoom_meeting_id = zoom_meeting.meeting_id
        call.zoom_join_url = zoom_meeting.join_url
        call.zoom_start_url = zoom_meeting.start_url
        call.outlook_event_id = event.event_id
        session.add(call)
        await session.flush()
        await self.notifications.queue_call_notifications(
            session, call, attendee_emails + [cmc.email])
        return call

    async def reschedule_call(
        self,
        session: AsyncSession,
        call: Call,
        start: datetime,
        end: datetime,
        timezone: str,
    ) -> Call:
        if call.status not in [
                CallStatus.needs_reschedule, CallStatus.cancelled
        ]:
            raise HTTPException(
                status_code=409,
                detail="Only missed or cancelled calls can be rescheduled")

        cmc = await session.get(User, call.cmc_user_id)
        if not cmc:
            raise HTTPException(status_code=404,
                                detail="Assigned CMC user not found")

        duration = int((end - start).total_seconds() / 60)
        slots = await self.get_available_slots(
            session,
            cmc,
            start,
            end,
            timezone,
            duration,
            exclude_call_id=call.id,
        )
        if not any(slot.start_time == start and slot.end_time == end
                   for slot in slots):
            raise HTTPException(status_code=409,
                                detail="Selected slot is no longer available")

        if call.zoom_meeting_id:
            await self.zoom.delete_meeting(call.zoom_meeting_id)
        if call.outlook_event_id:
            await self.graph.delete_calendar_event(
                cmc.microsoft_user_id or cmc.email, call.outlook_event_id)

        attendee_emails = await self._attendee_emails(session,
                                                      call.property_id, [])
        topic = "Transition follow-up call" if call.call_type == CallType.follow_up else "Transition first call"
        zoom_meeting = await self.zoom.create_meeting(
            host_zoom_user_id=cmc.zoom_user_id or cmc.email,
            topic=topic,
            start_time=start,
            duration_minutes=duration,
            timezone=timezone,
            agenda=f"{topic} for property {call.property_id}",
        )
        body_html = (
            f"<p>{topic}</p>"
            f"<p>Zoom link: <a href='{zoom_meeting.join_url}'>{zoom_meeting.join_url}</a></p>"
            "<p>Please join on time and have migration questions ready.</p>")
        event = await self.graph.create_calendar_event(
            organizer_email_or_id=cmc.microsoft_user_id or cmc.email,
            subject=topic,
            body_html=body_html,
            start=start,
            end=end,
            timezone=timezone,
            attendee_emails=attendee_emails,
        )

        call.start_time = start
        call.end_time = end
        call.timezone = timezone
        call.status = CallStatus.scheduled
        call.zoom_meeting_id = zoom_meeting.meeting_id
        call.zoom_join_url = zoom_meeting.join_url
        call.zoom_start_url = zoom_meeting.start_url
        call.outlook_event_id = event.event_id
        session.add(call)
        await session.flush()
        await self.notifications.queue_call_notifications(
            session, call, attendee_emails + [cmc.email])
        return call

    async def mark_call_missed(self, session: AsyncSession,
                               call: Call) -> Call:
        if call.status != CallStatus.scheduled:
            raise HTTPException(
                status_code=409,
                detail="Only scheduled calls can be marked as missed")
        call.status = CallStatus.needs_reschedule
        session.add(call)
        await session.flush()
        return call

    async def delete_call(self, session: AsyncSession, call: Call) -> None:
        cmc = await session.get(User, call.cmc_user_id)
        if cmc and call.zoom_meeting_id:
            await self.zoom.delete_meeting(call.zoom_meeting_id)
        if cmc and call.outlook_event_id:
            await self.graph.delete_calendar_event(
                cmc.microsoft_user_id or cmc.email, call.outlook_event_id)
        await session.execute(
            delete(Notification).where(Notification.call_id == call.id))
        await session.delete(call)
        await session.flush()

    async def transfer_future_calls(
        self,
        session: AsyncSession,
        property_id: str,
        old_cmc: User,
        new_cmc: User,
    ) -> int:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(Call).where(
                Call.property_id == property_id,
                Call.cmc_user_id == old_cmc.id,
                Call.status == CallStatus.scheduled,
                Call.start_time >= now,
            ))
        calls = list(result.scalars().all())
        for call in calls:
            # In a real implementation, cancel/recreate Outlook events because organizer changes are constrained.
            # This POC reassigns the call and queues a notification so the UI can show ownership transfer.
            call.cmc_user_id = new_cmc.id
            session.add(call)
            await self.notifications.queue_call_notifications(
                session, call, [new_cmc.email])
        await session.flush()
        return len(calls)

    async def _local_busy_intervals(
        self,
        session: AsyncSession,
        cmc_user_id: str,
        start: datetime,
        end: datetime,
        exclude_call_id: str | None = None,
    ) -> list[BusyInterval]:
        query = select(Call).where(
            and_(
                Call.cmc_user_id == cmc_user_id,
                Call.status.in_([CallStatus.scheduled, CallStatus.pending]),
                Call.start_time < end,
                Call.end_time > start,
            ))
        if exclude_call_id:
            query = query.where(Call.id != exclude_call_id)
        result = await session.execute(query)
        return [
            BusyInterval(call.start_time, call.end_time)
            for call in result.scalars().all()
        ]

    @staticmethod
    def _round_up(value: datetime, minutes: int) -> datetime:
        discard = timedelta(minutes=value.minute % minutes,
                            seconds=value.second,
                            microseconds=value.microsecond)
        if discard == timedelta(0):
            return value
        return value + (timedelta(minutes=minutes) - discard)

    @staticmethod
    def _overlaps_any(start: datetime, end: datetime,
                      intervals: list[BusyInterval]) -> bool:
        return any(start < interval.end_time and end > interval.start_time
                   for interval in intervals)

    @staticmethod
    def _merge_intervals(intervals: list[BusyInterval]) -> list[BusyInterval]:
        if not intervals:
            return []
        sorted_intervals = sorted(intervals, key=lambda item: item.start_time)
        merged = [sorted_intervals[0]]
        for item in sorted_intervals[1:]:
            last = merged[-1]
            if item.start_time <= last.end_time:
                merged[-1] = BusyInterval(last.start_time,
                                          max(last.end_time, item.end_time))
            else:
                merged.append(item)
        return merged

    async def _first_call_exists(self, session: AsyncSession,
                                 property_id: str) -> bool:
        result = await session.execute(
            select(Call).where(
                Call.property_id == property_id,
                Call.call_type == CallType.first_call,
                Call.status.in_([CallStatus.scheduled, CallStatus.completed]),
            ))
        return result.scalars().first() is not None

    async def _attendee_emails(self, session: AsyncSession, property_id: str,
                               attendee_user_ids: list[str]) -> list[str]:
        if attendee_user_ids:
            result = await session.execute(
                select(User).where(User.id.in_(attendee_user_ids)))
            return [user.email for user in result.scalars().all()]
        result = await session.execute(
            select(User).join(PropertyStaff,
                              PropertyStaff.user_id == User.id).where(
                                  PropertyStaff.property_id == property_id))
        return [user.email for user in result.scalars().all()]
