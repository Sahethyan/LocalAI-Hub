from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status

from app.services.ollama_client import OllamaClient, OllamaConnectionError


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


def get_ollama_client(request: Request) -> OllamaClient:
    client = request.app.state.ollama_client
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ollama client not initialized.",
        )
    return client


def ollama_unavailable(exc: OllamaConnectionError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    )
