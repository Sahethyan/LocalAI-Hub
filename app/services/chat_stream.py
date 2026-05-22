import logging
from collections.abc import AsyncIterator
from typing import Any

from app.config.settings import get_settings
from app.models.database import async_session_factory
from app.services.chat_service import ChatService
from app.services.model_validation import soft_validate_model
from app.services.ollama_client import OllamaClient, OllamaConnectionError

logger = logging.getLogger(__name__)

STREAM_EVENT_TOKEN = "token"
STREAM_EVENT_DONE = "done"
STREAM_EVENT_ERROR = "error"


def _token_from_chunk(chunk: dict[str, Any]) -> str:
    message = chunk.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


def _messages_for_ollama(messages: list) -> list[dict[str, str]]:
    return [{"role": m.role, "content": m.content} for m in messages]


def _error_event(detail: str) -> dict[str, Any]:
    return {"event": STREAM_EVENT_ERROR, "data": {"detail": detail}}


class ChatStreamService:
    """Orchestrate Ollama stream → persist messages (user deferred until first token)."""

    @staticmethod
    async def resolve_model(
        *,
        chat_model: str | None,
        request_model: str | None,
    ) -> str:
        model = request_model or chat_model
        if not model:
            raise ValueError("No model configured for this chat")
        return model

    @staticmethod
    async def _rollback_user_message(
        service: ChatService, user_message_id: int | None
    ) -> None:
        if user_message_id is not None:
            await service.delete_message(user_message_id)

    @staticmethod
    async def stream_reply(
        chat_id: int,
        user_content: str,
        model: str,
        ollama: OllamaClient,
        *,
        context_limit: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Yield stream events: token, done, or error.
        Each event is {"event": str, "data": dict}.
        User message is persisted on the first token; rolled back on failure.
        """
        limit = context_limit or get_settings().chat_context_messages

        try:
            model = await soft_validate_model(model, ollama)
        except OllamaConnectionError as exc:
            yield _error_event(str(exc))
            return
        except Exception as exc:
            logger.exception("Model validation failed for chat %s", chat_id)
            yield _error_event(f"Model validation failed: {exc}")
            return

        async with async_session_factory() as session:
            service = ChatService(session)
            chat = await service.get_chat(chat_id)
            if chat is None:
                yield _error_event("Chat not found")
                return

            history = await service.get_messages(chat_id)
            ollama_messages = _messages_for_ollama(history)
            ollama_messages.append({"role": "user", "content": user_content})
            if len(ollama_messages) > limit:
                ollama_messages = ollama_messages[-limit:]

            assistant_parts: list[str] = []
            user_message_id: int | None = None

            try:
                async for chunk in ollama.generate_stream(
                    model=model,
                    messages=ollama_messages,
                ):
                    token = _token_from_chunk(chunk)
                    if token:
                        if user_message_id is None:
                            user_message = await service.append_message(
                                chat_id, "user", user_content
                            )
                            if user_message is None:
                                yield _error_event("Chat not found")
                                return
                            user_message_id = user_message.id

                        assistant_parts.append(token)
                        yield {
                            "event": STREAM_EVENT_TOKEN,
                            "data": {"content": token},
                        }
                    if chunk.get("done"):
                        break
            except OllamaConnectionError as exc:
                logger.warning("Ollama stream failed for chat %s: %s", chat_id, exc)
                await ChatStreamService._rollback_user_message(
                    service, user_message_id
                )
                yield _error_event(str(exc))
                return
            except Exception as exc:
                logger.exception("Unexpected stream error for chat %s", chat_id)
                await ChatStreamService._rollback_user_message(
                    service, user_message_id
                )
                yield _error_event(f"Stream failed: {exc}")
                return

            full_content = "".join(assistant_parts)
            if not full_content:
                await ChatStreamService._rollback_user_message(
                    service, user_message_id
                )
                yield _error_event("Ollama returned an empty response")
                return

            assistant = await service.append_message(
                chat_id, "assistant", full_content
            )
            if assistant is None:
                await ChatStreamService._rollback_user_message(
                    service, user_message_id
                )
                yield _error_event("Failed to save assistant message")
                return

            if chat.model != model:
                chat.model = model
                await session.commit()

            yield {
                "event": STREAM_EVENT_DONE,
                "data": {
                    "message_id": assistant.id,
                    "chat_id": chat_id,
                    "content": full_content,
                },
            }
