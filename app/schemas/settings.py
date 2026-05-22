from pydantic import BaseModel, Field


class HubSettingsResponse(BaseModel):
    """Runtime hub settings exposed to the UI."""

    ollama_host: str = Field(..., description="Ollama host (IP or hostname)")
    ollama_port: int = Field(11434, ge=1, le=65535)
    chat_context_messages: int = Field(40, ge=1, le=200)
    ollama_base_url: str = Field(..., description="Resolved base URL sent to Ollama client")


class HubSettingsUpdate(BaseModel):
    ollama_host: str = Field(..., min_length=1, max_length=253)
    ollama_port: int = Field(11434, ge=1, le=65535)
    chat_context_messages: int = Field(40, ge=1, le=200)
