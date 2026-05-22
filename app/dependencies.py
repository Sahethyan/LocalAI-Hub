from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status

from app.config.settings import Settings, get_settings
from app.services.ollama_client import OllamaClient, OllamaConnectionError, build_ollama_client
from app.services.reconnect import OllamaReconnectMonitor


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


def get_ollama_client(
    request: Request,
    http_client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
    cfg: Annotated[Settings, Depends(get_settings)],
) -> OllamaClient:
    client = getattr(request.app.state, "ollama_client", None)
    if client is not None:
        return client
    return build_ollama_client(
        http_client,
        base_url=cfg.ollama_base_url,
        cache_ttl_seconds=float(cfg.ollama_cache_ttl_seconds),
        health_timeout_seconds=cfg.ollama_health_timeout_seconds,
    )


def get_ollama_monitor(request: Request) -> OllamaReconnectMonitor:
    monitor = getattr(request.app.state, "ollama_monitor", None)
    if monitor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ollama status monitor is not initialized.",
        )
    return monitor


def ollama_unavailable(exc: OllamaConnectionError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=str(exc),
    )
