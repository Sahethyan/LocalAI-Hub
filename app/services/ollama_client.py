import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OllamaConnectionError(Exception):
    """Raised when the Pi cannot reach Ollama on the laptop."""


def _connection_error(exc: httpx.RequestError) -> OllamaConnectionError:
    if isinstance(exc, httpx.ConnectError):
        return OllamaConnectionError(
            "Cannot connect to Ollama on the laptop. "
            "Is it running and reachable on the LAN?"
        )
    if isinstance(exc, httpx.TimeoutException):
        return OllamaConnectionError("Ollama request timed out.")
    return OllamaConnectionError(f"Ollama request failed: {exc}")


class OllamaClient:
    """Async HTTP client for Ollama on the inference laptop (Pi never loads models)."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        *,
        cache_ttl_seconds: float = 45.0,
        health_timeout_seconds: float = 3.0,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._cache_ttl = cache_ttl_seconds
        self._health_timeout = health_timeout_seconds
        self._models_cache: tuple[float, dict[str, Any]] | None = None

    @property
    def base_url(self) -> str:
        return self._base_url

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def invalidate_models_cache(self) -> None:
        self._models_cache = None

    async def health_check(self) -> bool:
        """Quick reachability probe (GET /api/tags, short timeout)."""
        try:
            response = await self._client.get(
                self._url("/api/tags"),
                timeout=self._health_timeout,
            )
            return response.is_success
        except httpx.RequestError as exc:
            logger.debug("Ollama health check failed: %s", exc)
            return False

    async def list_models(self, *, use_cache: bool = True) -> dict[str, Any]:
        """Proxy GET /api/tags; cache 30–60s on Pi to reduce LAN traffic."""
        now = time.monotonic()
        if use_cache and self._models_cache is not None:
            cached_at, data = self._models_cache
            if now - cached_at < self._cache_ttl:
                return data

        try:
            response = await self._client.get(self._url("/api/tags"))
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise OllamaConnectionError(
                f"Ollama returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise _connection_error(exc) from exc

        self._models_cache = (now, data)
        return data

    async def generate_stream(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        options: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream NDJSON chunks from POST /api/chat (stream=true)."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if options:
            payload["options"] = options

        try:
            async with self._client.stream(
                "POST",
                self._url("/api/chat"),
                json=payload,
                timeout=httpx.Timeout(300.0, connect=5.0),
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    raise OllamaConnectionError(
                        f"Ollama chat failed: HTTP {response.status_code}"
                    )
                async for line in response.aiter_lines():
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        yield json.loads(stripped)
                    except json.JSONDecodeError:
                        logger.warning(
                            "Invalid NDJSON line from Ollama: %s", stripped[:200]
                        )
        except httpx.RequestError as exc:
            raise _connection_error(exc) from exc

    async def generate_once(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Non-streaming POST /api/chat for one-shot verification."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if options:
            payload["options"] = options

        try:
            response = await self._client.post(
                self._url("/api/chat"),
                json=payload,
                timeout=httpx.Timeout(300.0, connect=5.0),
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise OllamaConnectionError(
                f"Ollama chat failed: HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise _connection_error(exc) from exc


def build_ollama_client(
    http_client: httpx.AsyncClient,
    *,
    base_url: str,
    cache_ttl_seconds: float,
    health_timeout_seconds: float,
) -> OllamaClient:
    return OllamaClient(
        http_client,
        base_url,
        cache_ttl_seconds=cache_ttl_seconds,
        health_timeout_seconds=health_timeout_seconds,
    )
