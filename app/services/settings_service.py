"""Persist and apply hub settings (Ollama URL, context window)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.models.database import AppSetting
from app.schemas.settings import HubSettingsResponse, HubSettingsUpdate
from app.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

SETTING_OLLAMA_HOST = "ollama_host"
SETTING_OLLAMA_PORT = "ollama_port"
SETTING_CHAT_CONTEXT = "chat_context_messages"

_HOST_PATTERN = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)


@dataclass
class RuntimeConfig:
    ollama_base_url: str
    chat_context_messages: int


def parse_ollama_url(url: str) -> tuple[str, int]:
    parsed = urlparse(url.strip())
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port if parsed.port is not None else 11434
    return host, port


def build_ollama_base_url(host: str, port: int) -> str:
    raw = host.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        if parsed.hostname:
            scheme = parsed.scheme or "http"
            p = parsed.port if parsed.port is not None else port
            return f"{scheme}://{parsed.hostname}:{p}".rstrip("/")
        return raw.rstrip("/")

    if not _HOST_PATTERN.match(raw) and raw not in ("localhost",):
        if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", raw):
            pass
        else:
            raise ValueError(f"Invalid Ollama host: {host!r}")

    return f"http://{raw}:{port}"


def runtime_from_env(cfg: Settings) -> RuntimeConfig:
    return RuntimeConfig(
        ollama_base_url=cfg.ollama_base_url.rstrip("/"),
        chat_context_messages=cfg.chat_context_messages,
    )


async def _get_setting(session: AsyncSession, key: str) -> str | None:
    row = await session.get(AppSetting, key)
    return row.value if row is not None else None


async def _set_setting(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(AppSetting, key)
    if row is None:
        session.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    await session.commit()


async def load_runtime_config(
    session: AsyncSession, cfg: Settings
) -> RuntimeConfig:
    """Merge SQLite overrides with .env defaults."""
    base = runtime_from_env(cfg)
    host = await _get_setting(session, SETTING_OLLAMA_HOST)
    port_s = await _get_setting(session, SETTING_OLLAMA_PORT)
    ctx_s = await _get_setting(session, SETTING_CHAT_CONTEXT)

    ollama_host, ollama_port = parse_ollama_url(base.ollama_base_url)
    if host is not None:
        ollama_host = host
    if port_s is not None:
        try:
            ollama_port = int(port_s)
        except ValueError:
            logger.warning("Invalid stored ollama_port %r; using default", port_s)

    chat_context = base.chat_context_messages
    if ctx_s is not None:
        try:
            chat_context = int(ctx_s)
        except ValueError:
            logger.warning("Invalid stored chat_context_messages %r", ctx_s)

    return RuntimeConfig(
        ollama_base_url=build_ollama_base_url(ollama_host, ollama_port),
        chat_context_messages=chat_context,
    )


def apply_runtime_config(app: FastAPI, runtime: RuntimeConfig) -> None:
    app.state.runtime_config = runtime
    client: OllamaClient | None = getattr(app.state, "ollama_client", None)
    if client is not None:
        client.set_base_url(runtime.ollama_base_url)
        logger.info("Ollama client base URL updated to %s", runtime.ollama_base_url)


async def bootstrap_runtime_settings(app: FastAPI, session: AsyncSession) -> None:
    cfg: Settings = app.state.settings
    runtime = await load_runtime_config(session, cfg)
    apply_runtime_config(app, runtime)


def get_runtime_config(app: FastAPI) -> RuntimeConfig:
    runtime = getattr(app.state, "runtime_config", None)
    if runtime is not None:
        return runtime
    cfg: Settings = app.state.settings
    return runtime_from_env(cfg)


def to_response(runtime: RuntimeConfig) -> HubSettingsResponse:
    host, port = parse_ollama_url(runtime.ollama_base_url)
    return HubSettingsResponse(
        ollama_host=host,
        ollama_port=port,
        chat_context_messages=runtime.chat_context_messages,
        ollama_base_url=runtime.ollama_base_url,
    )


async def get_settings_response(
    session: AsyncSession, app: FastAPI
) -> HubSettingsResponse:
    cfg: Settings = app.state.settings
    runtime = await load_runtime_config(session, cfg)
    return to_response(runtime)


async def update_settings(
    session: AsyncSession,
    app: FastAPI,
    body: HubSettingsUpdate,
) -> HubSettingsResponse:
    base_url = build_ollama_base_url(body.ollama_host, body.ollama_port)
    await _set_setting(session, SETTING_OLLAMA_HOST, body.ollama_host.strip())
    await _set_setting(session, SETTING_OLLAMA_PORT, str(body.ollama_port))
    await _set_setting(
        session, SETTING_CHAT_CONTEXT, str(body.chat_context_messages)
    )

    runtime = RuntimeConfig(
        ollama_base_url=base_url,
        chat_context_messages=body.chat_context_messages,
    )
    apply_runtime_config(app, runtime)
    return to_response(runtime)
