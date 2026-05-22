import json
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import get_ollama_client, ollama_unavailable
from app.schemas.ollama import GenerateRequest
from app.services.ollama_client import OllamaClient, OllamaConnectionError

router = APIRouter()


@router.post("/generate")
async def generate(
    body: GenerateRequest,
    ollama: Annotated[OllamaClient, Depends(get_ollama_client)],
):
    """Stream NDJSON from Ollama /api/chat (Pi proxies, never runs inference)."""
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
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
