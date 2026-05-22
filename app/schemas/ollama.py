from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

OllamaConnectionStatus = Literal["online", "offline", "degraded"]


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
    status: OllamaConnectionStatus
    ollama_base_url: str
    last_success_at: datetime | None = None
    last_check_at: datetime | None = None
    message: str | None = None


class OllamaChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1)


class OllamaGenerateRequest(BaseModel):
    model: str = Field(..., min_length=1)
    messages: list[OllamaChatMessage] = Field(..., min_length=1)
    stream: bool = True


class OllamaGenerateChunk(BaseModel):
    """Single NDJSON chunk from Ollama /api/chat (stream=true)."""

    model: str | None = None
    created_at: str | None = None
    message: dict[str, Any] | None = None
    done: bool = False
    done_reason: str | None = None
    total_duration: int | None = None
    load_duration: int | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None
