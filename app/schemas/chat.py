from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MessageRole = Literal["user", "assistant", "system"]

TITLE_MAX_LEN = 50
MESSAGE_CONTENT_MAX_LEN = 32_000


class ChatCreate(BaseModel):
    title: str | None = None
    model: str | None = None


class ChatSummary(BaseModel):
    id: int
    title: str
    model: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    role: MessageRole
    content: str = Field(..., min_length=1, max_length=MESSAGE_CONTENT_MAX_LEN)


class MessageResponse(BaseModel):
    id: int
    chat_id: int
    role: MessageRole
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatDetail(BaseModel):
    id: int
    title: str
    model: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]

    model_config = {"from_attributes": True}


class StreamMessageCreate(BaseModel):
    """Send a user message and stream the assistant reply."""

    content: str = Field(..., min_length=1, max_length=MESSAGE_CONTENT_MAX_LEN)
    model: str | None = Field(
        default=None,
        min_length=1,
        description="Overrides chat.model when set",
    )


class StreamTokenPayload(BaseModel):
    content: str


class StreamDonePayload(BaseModel):
    message_id: int
    chat_id: int
    content: str


class StreamErrorPayload(BaseModel):
    detail: str
