import time
from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_ollama_client
from app.schemas.ollama import OllamaStatusResponse
from app.services.ollama_client import OllamaClient

router = APIRouter()


@router.get("/status", response_model=OllamaStatusResponse)
async def ollama_status(
    ollama: Annotated[OllamaClient, Depends(get_ollama_client)],
) -> OllamaStatusResponse:
    """Ollama reachability for UI polling (every 5s)."""
    started = time.perf_counter()
    online = await ollama.health_check()
    latency_ms = round((time.perf_counter() - started) * 1000, 1)

    if online:
        return OllamaStatusResponse(ollama="online", latency_ms=latency_ms)
    return OllamaStatusResponse(ollama="offline", latency_ms=None)
