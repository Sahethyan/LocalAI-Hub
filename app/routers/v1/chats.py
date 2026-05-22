from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session_factory
from app.schemas.chat import (
    ChatCreate,
    ChatDetail,
    ChatSummary,
    MessageCreate,
    MessageResponse,
)
from app.services.chat_service import ChatService

router = APIRouter()


async def get_db_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


def get_chat_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ChatService:
    return ChatService(session)


@router.post("/chat", response_model=ChatSummary, status_code=status.HTTP_201_CREATED)
async def create_chat(
    body: ChatCreate,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatSummary:
    chat = await service.create_chat(title=body.title, model=body.model)
    return ChatSummary.model_validate(chat)


@router.get("/chats", response_model=list[ChatSummary])
async def list_chats(
    service: Annotated[ChatService, Depends(get_chat_service)],
    limit: int = 50,
    offset: int = 0,
) -> list[ChatSummary]:
    chats = await service.list_chats(limit=limit, offset=offset)
    return [ChatSummary.model_validate(c) for c in chats]


@router.get("/chats/{chat_id}", response_model=ChatDetail)
async def get_chat(
    chat_id: int,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatDetail:
    chat = await service.get_chat_with_messages(chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return ChatDetail.model_validate(chat)


@router.delete("/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: int,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> None:
    deleted = await service.delete_chat(chat_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")


@router.post(
    "/chats/{chat_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def append_message(
    chat_id: int,
    body: MessageCreate,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> MessageResponse:
    message = await service.append_message(chat_id, body.role, body.content)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return MessageResponse.model_validate(message)
