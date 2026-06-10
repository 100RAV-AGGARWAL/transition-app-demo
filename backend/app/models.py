from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    staff = "staff"
    owner = "owner"
    cmc = "cmc"
    admin = "admin"


class TransitionStatus(str, enum.Enum):
    not_started = "not_started"
    training_in_progress = "training_in_progress"
    first_call_pending = "first_call_pending"
    in_progress = "in_progress"
    go_live_ready = "go_live_ready"
    completed = "completed"
    blocked = "blocked"


class AssignmentStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class CallType(str, enum.Enum):
    first_call = "first_call"
    follow_up = "follow_up"


class CallStatus(str, enum.Enum):
    scheduled = "scheduled"
    pending = "pending"
    completed = "completed"
    cancelled = "cancelled"
    needs_reschedule = "needs_reschedule"


class NotificationStatus(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36),
                                    primary_key=True,
                                    default=new_uuid)
    email: Mapped[str] = mapped_column(String(255),
                                       unique=True,
                                       nullable=False,
                                       index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    zoom_user_id: Mapped[str | None] = mapped_column(String(255),
                                                     nullable=True)
    microsoft_user_id: Mapped[str | None] = mapped_column(String(255),
                                                          nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utc_now)

    owned_properties: Mapped[list[Property]] = relationship(
        back_populates="owner", foreign_keys="Property.owner_user_id")
    staff_memberships: Mapped[list[PropertyStaff]] = relationship(
        back_populates="user")
    cmc_assignments: Mapped[list[CmcAssignment]] = relationship(
        back_populates="cmc_user", foreign_keys="CmcAssignment.cmc_user_id")
    chat_threads: Mapped[list["ChatThread"]] = relationship(
        back_populates="cmc_user", foreign_keys="ChatThread.cmc_user_id")
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="sender", foreign_keys="ChatMessage.sender_user_id")


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String(36),
                                    primary_key=True,
                                    default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    old_tool_property_id: Mapped[str | None] = mapped_column(String(120),
                                                             nullable=True)
    new_tool_property_id: Mapped[str | None] = mapped_column(String(120),
                                                             nullable=True)
    transition_status: Mapped[TransitionStatus] = mapped_column(
        Enum(TransitionStatus), default=TransitionStatus.not_started)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"),
                                               nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utc_now)

    owner: Mapped[User] = relationship(back_populates="owned_properties",
                                       foreign_keys=[owner_user_id])
    staff: Mapped[list[PropertyStaff]] = relationship(
        back_populates="property")
    assignments: Mapped[list[CmcAssignment]] = relationship(
        back_populates="property")
    training_statuses: Mapped[list[TrainingStatus]] = relationship(
        back_populates="property")
    calls: Mapped[list[Call]] = relationship(back_populates="property")
    chat_threads: Mapped[list["ChatThread"]] = relationship(
        back_populates="property")


class PropertyStaff(Base):
    __tablename__ = "property_staff"
    __table_args__ = (UniqueConstraint("property_id",
                                       "user_id",
                                       name="uq_property_staff_user"), )

    id: Mapped[str] = mapped_column(String(36),
                                    primary_key=True,
                                    default=new_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"),
                                             nullable=False,
                                             index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"),
                                         nullable=False,
                                         index=True)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_primary_contact: Mapped[bool] = mapped_column(Boolean, default=False)

    property: Mapped[Property] = relationship(back_populates="staff")
    user: Mapped[User] = relationship(back_populates="staff_memberships")


class CmcAssignment(Base):
    __tablename__ = "cmc_assignments"

    id: Mapped[str] = mapped_column(String(36),
                                    primary_key=True,
                                    default=new_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"),
                                             nullable=False,
                                             index=True)
    cmc_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"),
                                             nullable=False,
                                             index=True)
    assigned_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"),
                                                     nullable=False)
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus), default=AssignmentStatus.active)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  default=utc_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                      nullable=True)
    first_call_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    property: Mapped[Property] = relationship(back_populates="assignments")
    cmc_user: Mapped[User] = relationship(back_populates="cmc_assignments",
                                          foreign_keys=[cmc_user_id])
    assigned_by: Mapped[User] = relationship(
        foreign_keys=[assigned_by_user_id])


class TrainingStatus(Base):
    __tablename__ = "training_statuses"
    __table_args__ = (UniqueConstraint("property_id",
                                       "user_id",
                                       name="uq_training_property_user"), )

    id: Mapped[str] = mapped_column(String(36),
                                    primary_key=True,
                                    default=new_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"),
                                             nullable=False,
                                             index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"),
                                         nullable=False,
                                         index=True)
    external_training_id: Mapped[str | None] = mapped_column(String(255),
                                                             nullable=True)
    status: Mapped[str] = mapped_column(String(120), default="not_started")
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    required_modules: Mapped[int] = mapped_column(Integer, default=0)
    completed_modules: Mapped[int] = mapped_column(Integer, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    property: Mapped[Property] = relationship(
        back_populates="training_statuses")
    user: Mapped[User] = relationship()


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(String(36),
                                    primary_key=True,
                                    default=new_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"),
                                             nullable=False,
                                             index=True)
    cmc_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"),
                                             nullable=False,
                                             index=True)
    scheduled_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"),
                                                      nullable=False)
    call_type: Mapped[CallType] = mapped_column(Enum(CallType), nullable=False)
    status: Mapped[CallStatus] = mapped_column(Enum(CallStatus),
                                               default=CallStatus.scheduled)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 nullable=False,
                                                 index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                               nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    zoom_meeting_id: Mapped[str | None] = mapped_column(String(255),
                                                        nullable=True)
    zoom_join_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    zoom_start_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    outlook_event_id: Mapped[str | None] = mapped_column(String(255),
                                                         nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utc_now,
                                                 onupdate=utc_now)

    property: Mapped[Property] = relationship(back_populates="calls")
    cmc_user: Mapped[User] = relationship(foreign_keys=[cmc_user_id])
    scheduled_by: Mapped[User] = relationship(
        foreign_keys=[scheduled_by_user_id])
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="call",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChatThread(Base):
    __tablename__ = "chat_threads"

    id: Mapped[str] = mapped_column(String(36),
                                    primary_key=True,
                                    default=new_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"),
                                             nullable=False,
                                             index=True)
    cmc_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"),
                                             nullable=False,
                                             index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utc_now)

    property: Mapped[Property] = relationship(back_populates="chat_threads")
    cmc_user: Mapped[User] = relationship(back_populates="chat_threads",
                                          foreign_keys=[cmc_user_id])
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="thread",
        order_by="ChatMessage.created_at",
        cascade="all, delete-orphan",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36),
                                    primary_key=True,
                                    default=new_uuid)
    thread_id: Mapped[str] = mapped_column(ForeignKey("chat_threads.id"),
                                           nullable=False,
                                           index=True)
    sender_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"),
                                                nullable=False,
                                                index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utc_now)
    read_by: Mapped[list[str]] = mapped_column(JSON, default=list)

    thread: Mapped[ChatThread] = relationship(back_populates="messages")
    sender: Mapped[User] = relationship(back_populates="chat_messages",
                                        foreign_keys=[sender_user_id])


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36),
                                    primary_key=True,
                                    default=new_uuid)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id",
                                                    ondelete="CASCADE"),
                                         nullable=False,
                                         index=True)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(80), nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                     nullable=True)
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus), default=NotificationStatus.queued)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    call: Mapped[Call] = relationship(back_populates="notifications")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36),
                                    primary_key=True,
                                    default=new_uuid)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"),
                                                      nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utc_now)

    actor: Mapped[User | None] = relationship()
