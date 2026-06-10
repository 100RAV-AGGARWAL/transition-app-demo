from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import get_current_user
from ..database import get_session
from ..models import (AssignmentStatus, ChatMessage, ChatThread, CmcAssignment,
                      Property, PropertyStaff, User, UserRole)
from ..schemas import (ChatMessageOut, ChatThreadOut, CreateChatThreadRequest,
                       SendChatMessageRequest)

router = APIRouter(prefix="/chat", tags=["chat"])


class ConnectionManager:

    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, thread_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.setdefault(thread_id, []).append(websocket)

    def disconnect(self, thread_id: str, websocket: WebSocket) -> None:
        connections = self.active_connections.get(thread_id)
        if connections and websocket in connections:
            connections.remove(websocket)
            if not connections:
                self.active_connections.pop(thread_id, None)

    async def broadcast(self, thread_id: str, message: dict) -> None:
        for connection in list(self.active_connections.get(thread_id, [])):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(thread_id, connection)

    async def broadcast_others(self, thread_id: str, message: dict,
                               websocket: WebSocket) -> None:
        for connection in list(self.active_connections.get(thread_id, [])):
            if connection is websocket:
                continue
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(thread_id, connection)


manager = ConnectionManager()


def _thread_to_out(thread: ChatThread, current_user_id: str) -> ChatThreadOut:
    messages = list(thread.messages or [])
    last_message = messages[-1].content if messages else None
    last_activity_at = messages[
        -1].created_at if messages else thread.created_at
    unread_count = sum(1 for message in messages
                       if current_user_id not in (message.read_by or []))
    return ChatThreadOut(
        id=thread.id,
        property=thread.property,
        cmc_user=thread.cmc_user,
        last_message=last_message,
        last_activity_at=last_activity_at,
        unread_count=unread_count,
    )


async def _assert_property_access(session: AsyncSession, user: User,
                                  property_id: str) -> None:
    if user.is_admin or user.role == UserRole.admin:
        return
    if user.role == UserRole.cmc:
        result = await session.execute(
            select(CmcAssignment.id).where(
                CmcAssignment.property_id == property_id,
                CmcAssignment.cmc_user_id == user.id,
                CmcAssignment.status == AssignmentStatus.active,
            ))
        if result.first():
            return
    elif user.role == UserRole.owner:
        result = await session.execute(
            select(Property.id).where(Property.id == property_id,
                                      Property.owner_user_id == user.id))
        if result.first():
            return
    else:
        result = await session.execute(
            select(PropertyStaff.id).where(
                PropertyStaff.property_id == property_id,
                PropertyStaff.user_id == user.id,
            ))
        if result.first():
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail="No access to this property")


async def _assert_thread_access(session: AsyncSession, user: User,
                                thread_id: str) -> ChatThread:
    result = await session.execute(
        select(ChatThread).options(selectinload(ChatThread.property),
                                   selectinload(ChatThread.cmc_user)).where(
                                       ChatThread.id == thread_id))
    thread = result.scalars().first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Chat thread not found")

    if user.is_admin or user.role == UserRole.admin:
        return thread

    if user.role == UserRole.cmc:
        if thread.cmc_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Access denied to this thread")
        return thread

    if user.role == UserRole.owner and thread.property.owner_user_id == user.id:
        return thread

    result = await session.execute(
        select(PropertyStaff.id).where(
            PropertyStaff.property_id == thread.property_id,
            PropertyStaff.user_id == user.id,
        ))
    if result.first():
        return thread

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied to this thread")


@router.get("/threads", response_model=list[ChatThreadOut])
async def list_chat_threads(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
) -> list[ChatThreadOut]:
    query = select(ChatThread).options(
        selectinload(ChatThread.property),
        selectinload(ChatThread.cmc_user),
        selectinload(ChatThread.messages),
    )
    if user.role == UserRole.cmc:
        query = query.where(ChatThread.cmc_user_id == user.id)
    elif user.role == UserRole.owner:
        query = query.join(Property).where(Property.owner_user_id == user.id)
    else:
        query = query.join(Property).join(
            Property.staff).where(PropertyStaff.user_id == user.id)

    result = await session.execute(query.order_by(ChatThread.id.desc()))
    threads = list(result.scalars().unique().all())
    return [_thread_to_out(thread, user.id) for thread in threads]


@router.post("/threads", response_model=ChatThreadOut)
async def create_chat_thread(
        payload: CreateChatThreadRequest,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
) -> ChatThreadOut:
    await _assert_property_access(session, user, payload.property_id)

    result = await session.execute(
        select(CmcAssignment).where(
            CmcAssignment.property_id == payload.property_id,
            CmcAssignment.status == AssignmentStatus.active,
        ))
    assignment = result.scalars().first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="No active CMC assignment for property")

    result = await session.execute(
        select(ChatThread).where(
            ChatThread.property_id == payload.property_id,
            ChatThread.cmc_user_id == assignment.cmc_user_id,
        ))
    thread = result.scalars().first()
    if not thread:
        thread = ChatThread(property_id=payload.property_id,
                            cmc_user_id=assignment.cmc_user_id)
        session.add(thread)
        await session.commit()
        # reload thread with related objects to avoid lazy-loading outside
        # of async context
        result = await session.execute(
            select(ChatThread).options(
                selectinload(ChatThread.property),
                selectinload(ChatThread.cmc_user),
                selectinload(ChatThread.messages),
            ).where(ChatThread.id == thread.id))
        thread = result.scalars().first()
    return _thread_to_out(thread, user.id)


@router.get("/threads/{thread_id}/messages",
            response_model=list[ChatMessageOut])
async def get_thread_messages(
        thread_id: str,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
) -> list[ChatMessageOut]:
    thread = await _assert_thread_access(session, user, thread_id)
    result = await session.execute(
        select(ChatMessage).options(selectinload(ChatMessage.sender)).where(
            ChatMessage.thread_id == thread.id).order_by(
                ChatMessage.created_at))
    messages = result.scalars().all()
    for message in messages:
        if user.id not in (message.read_by or []):
            message.read_by = list(message.read_by or []) + [user.id]
    await session.commit()
    return [ChatMessageOut.from_orm(message) for message in messages]


@router.post("/threads/{thread_id}/messages", response_model=ChatMessageOut)
async def send_thread_message(
        thread_id: str,
        payload: SendChatMessageRequest,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
) -> ChatMessageOut:
    thread = await _assert_thread_access(session, user, thread_id)
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Message content cannot be empty")

    message = ChatMessage(thread_id=thread.id,
                          sender_user_id=user.id,
                          content=content,
                          read_by=[user.id])
    session.add(message)
    await session.commit()
    await session.refresh(message)
    await session.refresh(message.sender)

    message_out = ChatMessageOut.from_orm(message)
    await manager.broadcast(thread.id, {
        "type": "message",
        "message": message_out.model_dump()
    })
    return message_out


@router.post("/threads/{thread_id}/read")
async def mark_thread_read(
        thread_id: str,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
) -> dict:
    thread = await _assert_thread_access(session, user, thread_id)
    result = await session.execute(
        select(ChatMessage).where(ChatMessage.thread_id == thread.id))
    messages = result.scalars().all()
    updated = False
    for message in messages:
        if user.id not in (message.read_by or []):
            message.read_by = list(message.read_by or []) + [user.id]
            updated = True
    if updated:
        await session.commit()
    await manager.broadcast(thread.id, {
        "type": "read",
        "thread_id": thread.id,
        "user_id": user.id
    })
    return {"status": "ok"}


@router.websocket("/ws")
async def websocket_chat(
        websocket: WebSocket,
        thread_id: str,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
) -> None:
    thread = await _assert_thread_access(session, user, thread_id)
    await manager.connect(thread_id, websocket)
    await manager.broadcast_others(thread_id, {
        "type": "typing",
        "user_id": user.id,
        "status": "connected"
    }, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if not isinstance(data, dict):
                continue
            event_type = data.get("type")
            if event_type == "typing":
                await manager.broadcast_others(
                    thread_id, {
                        "type": "typing",
                        "user_id": user.id,
                        "is_typing": bool(data.get("is_typing", True)),
                    }, websocket)
            elif event_type == "read":
                await mark_thread_read(thread_id, user, session)
            elif event_type == "message":
                content = str(data.get("content", "")).strip()
                if not content:
                    continue
                message = ChatMessage(thread_id=thread.id,
                                      sender_user_id=user.id,
                                      content=content,
                                      read_by=[user.id])
                session.add(message)
                await session.commit()
                await session.refresh(message)
                await session.refresh(message.sender)
                await manager.broadcast(
                    thread_id, {
                        "type": "message",
                        "message":
                        ChatMessageOut.from_orm(message).model_dump()
                    })
    except WebSocketDisconnect:
        manager.disconnect(thread_id, websocket)
