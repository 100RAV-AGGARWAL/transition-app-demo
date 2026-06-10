from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import CallStatus, CallType, TransitionStatus, UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    is_admin: bool = False
    zoom_user_id: str | None = None


class PropertyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    address: str
    old_tool_property_id: str | None = None
    new_tool_property_id: str | None = None
    transition_status: TransitionStatus
    owner_user_id: str


class TrainingStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    property_id: str
    user_id: str
    status: str
    progress_percent: int
    required_modules: int
    completed_modules: int
    last_synced_at: datetime | None = None


class StaffTrainingOut(BaseModel):
    user: UserOut
    training: TrainingStatusOut | None = None
    title: str | None = None
    is_primary_contact: bool = False


class AssignmentOut(BaseModel):
    id: str
    property: PropertyOut
    cmc: UserOut
    assigned_at: datetime
    first_call_due_at: datetime | None = None
    first_call_status: str


class CallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    property_id: str
    cmc_user_id: str
    scheduled_by_user_id: str
    call_type: CallType
    status: CallStatus
    start_time: datetime
    end_time: datetime
    timezone: str
    zoom_join_url: str | None = None
    outlook_event_id: str | None = None


class SlotOut(BaseModel):
    start_time: datetime
    end_time: datetime
    timezone: str


class BookCallRequest(BaseModel):
    property_id: str
    call_type: CallType
    start_time: datetime
    end_time: datetime
    timezone: str = "Asia/Kolkata"
    attendee_user_ids: list[str] = Field(default_factory=list)


class RescheduleCallRequest(BaseModel):
    start_time: datetime
    end_time: datetime
    timezone: str = "Asia/Kolkata"


class CreateChatThreadRequest(BaseModel):
    property_id: str


class SendChatMessageRequest(BaseModel):
    content: str


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    thread_id: str
    sender: UserOut
    content: str
    created_at: datetime
    read_by: list[str] = Field(default_factory=list)


class ChatThreadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    property: PropertyOut
    cmc_user: UserOut
    last_message: str | None = None
    last_activity_at: datetime
    unread_count: int = 0


class AssignCmcRequest(BaseModel):
    property_id: str
    cmc_user_id: str
    first_call_due_at: datetime | None = None


class ReassignCmcRequest(BaseModel):
    property_id: str
    new_cmc_user_id: str
    transfer_future_calls: bool = True
    reason: str | None = None


class PropertyDashboardOut(BaseModel):
    user: UserOut
    properties: list[PropertyOut]
    calls: list[CallOut]


class DashboardCountsOut(BaseModel):
    properties: int
    staff_users: int
    cmcs: int
    open_first_calls: int
    scheduled_calls: int


class AdminDashboardOut(BaseModel):
    user: UserOut
    counts: DashboardCountsOut
    properties: list[PropertyOut]
    cmcs: list[UserOut]
