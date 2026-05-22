import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config.settings import PROJECT_ROOT, get_settings
from app.models.database import init_db
from app.routers.v1 import api_v1_router
from app.services.ollama_client import build_ollama_client
from app.services.reconnect import OllamaReconnectMonitor
from app.utils.lan_check import LanOnlyMiddleware
from app.utils.logging import setup_logging
from app.utils.rate_limit import limiter

logger = logging.getLogger(__name__)

TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_settings()
    app.state.settings = cfg

    await init_db()
    logger.info("Database initialized at %s", cfg.database_path)

    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=3.0),
        limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
    )
    app.state.ollama_client = build_ollama_client(
        app.state.http_client,
        base_url=cfg.ollama_base_url,
        cache_ttl_seconds=float(cfg.ollama_cache_ttl_seconds),
        health_timeout_seconds=cfg.ollama_health_timeout_seconds,
    )
    app.state.ollama_monitor = OllamaReconnectMonitor(
        app.state.ollama_client,
        interval_seconds=float(cfg.ollama_reconnect_interval_seconds),
    )
    app.state.ollama_monitor.start()
    logger.info("HTTP client pool ready (Ollama: %s)", cfg.ollama_base_url)

    yield

    await app.state.ollama_monitor.stop()
    await app.state.http_client.aclose()
    logger.info("HTTP client pool closed")


def _cors_origins(cfg) -> list[str]:
    if cfg.cors_origin_list:
        return cfg.cors_origin_list
    if cfg.lan_only:
        return []
    return ["*"]


def create_app() -> FastAPI:
    setup_logging()
    cfg = get_settings()

    app = FastAPI(
        title="LocalAI Hub",
        description="Lightweight local AI web interface for Raspberry Pi",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(LanOnlyMiddleware)

    origins = _cors_origins(cfg)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else ["http://localhost", "http://127.0.0.1"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(api_v1_router)

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    templates = None
    if TEMPLATES_DIR.is_dir():
        templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
        app.state.templates = templates

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index(request: Request):
        if templates is None:
            return HTMLResponse(
                "<h1>LocalAI Hub</h1><p>API running. See <a href='/docs'>/docs</a>.</p>"
            )
        return templates.TemplateResponse(
            request=request,
            name="base.html",
            context={"title": "LocalAI Hub"},
        )

    return app


app = create_app()
