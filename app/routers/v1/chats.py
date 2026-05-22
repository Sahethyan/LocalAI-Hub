from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.dependencies import get_ollama_client, ollama_unavailable
from app.models.database import async_session_factory
from app.schemas.chat import (
    ChatCreate,
    ChatDetail,
    ChatSummary,
    MessageCreate,
    MessageResponse,
    StreamMessageCreate,
)
from app.services.chat_service import ChatService
from app.services.chat_stream import (
    STREAM_EVENT_ERROR,
    ChatStreamService,
)
from app.services.ollama_client import OllamaClient, OllamaConnectionError
from app.utils.sse import format_sse_json

router = APIRouter()


async def get_db_session() -> AsyncIterator[AsyncSession]:
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
    responses={
        200: {
            "description": "SSE stream (token, done, error events)",
            "content": {"text/event-stream": {}},
        },
        201: {"description": "Message saved (stream=false)"},
    },
)
async def send_message(
    chat_id: int,
    body: StreamMessageCreate,
    ollama: Annotated[OllamaClient, Depends(get_ollama_client)],
    cfg: Annotated[Settings, Depends(get_settings)],
    stream: Annotated[
        bool,
        Query(description="Stream assistant reply via SSE when true"),
    ] = True,
    service: Annotated[ChatService, Depends(get_chat_service)],
):
    """
    Send a user message. By default streams the assistant reply as SSE.
    Set stream=false to append a user message only (no Ollama call).
    """
    if not stream:
        message = await service.append_message(chat_id, "user", body.content)
        if message is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found"
            )
        return MessageResponse.model_validate(message)

    chat = await service.get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    try:
        model = await ChatStreamService.resolve_model(
            chat_model=chat.model,
            request_model=body.model,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    async def sse_events() -> AsyncIterator[str]:
        try:
            async for item in ChatStreamService.stream_reply(
                chat_id,
                body.content,
                model,
                ollama,
                context_limit=cfg.chat_context_messages,
            ):
                yield format_sse_json(item["event"], item["data"])
        except OllamaConnectionError as exc:
            yield format_sse_json(STREAM_EVENT_ERROR, {"detail": str(exc)})

    return StreamingResponse(
        sse_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/chats/{chat_id}/messages/raw",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def append_message_raw(
    chat_id: int,
    body: MessageCreate,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> MessageResponse:
    """Append an arbitrary role/message without streaming (internal/testing)."""
    message = await service.append_message(chat_id, body.role, body.content)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return MessageResponse.model_validate(message)
