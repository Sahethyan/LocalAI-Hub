from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class OllamaModelDetails(BaseModel):
    parent_model: str | None = None
    format: str | None = None
    family: str | None = None
    families: list[str] | None = None
    parameter_size: str | None = None
    quantization_level: str | None = None


class OllamaModelInfo(BaseModel):
    name: str
    model: str | None = None
    modified_at: datetime | None = None
    size: int | None = None
    digest: str | None = None
    details: OllamaModelDetails | None = None


class OllamaModelsResponse(BaseModel):
    models: list[OllamaModelInfo] = Field(default_factory=list)


class OllamaStatusResponse(BaseModel):
    ollama: Literal["online", "offline"]
    latency_ms: float | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1, max_length=32000)


class GenerateRequest(BaseModel):
    model: str = Field(..., min_length=1, max_length=128)
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=80)
    stream: bool = True
