import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import (
    get_ollama_client,
    get_ollama_monitor,
    ollama_unavailable,
)
from app.schemas.ollama import OllamaGenerateRequest, OllamaStatusResponse
from app.services.ollama_client import OllamaClient, OllamaConnectionError
from app.services.reconnect import OllamaReconnectMonitor

router = APIRouter(prefix="/ollama")


@router.get("/status", response_model=OllamaStatusResponse)
async def ollama_status(
    monitor: Annotated[OllamaReconnectMonitor, Depends(get_ollama_monitor)],
    ollama: Annotated[OllamaClient, Depends(get_ollama_client)],
) -> OllamaStatusResponse:
    """Connection indicator data for UI polling."""
    snap = monitor.snapshot()
    return OllamaStatusResponse(
        status=snap["status"],
        ollama_base_url=ollama.base_url,
        last_success_at=snap["last_success_at"],
        last_check_at=snap["last_check_at"],
        message=snap["message"],
    )


@router.post("/generate")
async def generate(
    body: OllamaGenerateRequest,
    ollama: Annotated[OllamaClient, Depends(get_ollama_client)],
) -> Any:
    """One-shot or streaming generate via Ollama /api/chat (Phase 3 verification)."""
    messages = [m.model_dump() for m in body.messages]

    if not body.stream:
        try:
            return await ollama.generate_once(model=body.model, messages=messages)
        except OllamaConnectionError as exc:
            raise ollama_unavailable(exc) from exc

    async def ndjson_stream():
        try:
            async for chunk in ollama.generate_stream(
                model=body.model, messages=messages
            ):
                yield json.dumps(chunk) + "\n"
        except OllamaConnectionError as exc:
            yield json.dumps({"error": str(exc), "done": True}) + "\n"

    return StreamingResponse(
        ndjson_stream(),
        media_type="application/x-ndjson",
    )
