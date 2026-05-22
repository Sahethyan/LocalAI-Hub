import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from app.schemas.chat import StreamMessageCreate
from app.services.chat_service import ChatService
from app.services.chat_stream import ChatStreamService
from app.models.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter()


def _ws_payload(event: str, data: dict) -> dict:
    """Same token protocol as SSE: event name plus payload fields."""
    return {"event": event, **data}


@router.websocket("/ws/chats/{chat_id}")
async def chat_websocket(websocket: WebSocket, chat_id: int) -> None:
    """
    Bidirectional chat stream. Client sends JSON:
    {"content": "...", "model": "optional"}.
    Server replies with {"event": "token"|"done"|"error", ...}.
    """
    await websocket.accept()
    ollama = websocket.app.state.ollama_client
    cfg = websocket.app.state.settings

    try:
        while True:
            try:
                raw = await websocket.receive_json()
            except ValueError:
                await websocket.send_json(
                    _ws_payload("error", {"detail": "Invalid JSON message"})
                )
                continue

            try:
                body = StreamMessageCreate.model_validate(raw)
            except ValidationError as exc:
                await websocket.send_json(
                    _ws_payload("error", {"detail": exc.errors()[0]["msg"]})
                )
                continue

            async with async_session_factory() as session:
                chat = await ChatService(session).get_chat(chat_id)
            if chat is None:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            try:
                model = await ChatStreamService.resolve_model(
                    chat_model=chat.model,
                    request_model=body.model,
                )
            except ValueError as exc:
                await websocket.send_json(_ws_payload("error", {"detail": str(exc)}))
                continue

            async for item in ChatStreamService.stream_reply(
                chat_id,
                body.content,
                model,
                ollama,
                context_limit=cfg.chat_context_messages,
            ):
                await websocket.send_json(_ws_payload(item["event"], item["data"]))

    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected for chat %s", chat_id)
