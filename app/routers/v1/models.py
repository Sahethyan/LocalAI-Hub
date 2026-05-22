from typing import Annotated

from fastapi import APIRouter, Depends

from app.config.settings import Settings, get_settings
from app.dependencies import get_ollama_client, ollama_unavailable
from app.schemas.ollama import OllamaModelsResponse
from app.services.ollama_client import OllamaClient, OllamaConnectionError

router = APIRouter()


@router.get("/models", response_model=OllamaModelsResponse)
async def list_models(
    ollama: Annotated[OllamaClient, Depends(get_ollama_client)],
) -> OllamaModelsResponse:
    """Proxy Ollama GET /api/tags (cached on Pi)."""
    try:
        data = await ollama.list_models()
    except OllamaConnectionError as exc:
        raise ollama_unavailable(exc) from exc
    return OllamaModelsResponse.model_validate(data)
