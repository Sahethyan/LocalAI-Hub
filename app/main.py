import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config.settings import PROJECT_ROOT, get_settings
from app.routers.v1 import api_v1_router
from app.services.ollama_client import build_ollama_client
from app.utils.lan_check import LanOnlyMiddleware
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)

TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_settings()
    app.state.settings = cfg

    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=3.0),
        limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
        trust_env=False,
    )
    app.state.ollama_client = build_ollama_client(
        app.state.http_client,
        base_url=cfg.ollama_base_url,
        cache_ttl_seconds=float(cfg.ollama_cache_ttl_seconds),
        health_timeout_seconds=cfg.ollama_health_timeout_seconds,
    )
    logger.info("Ollama proxy ready: %s", cfg.ollama_base_url)

    yield

    await app.state.http_client.aclose()
    logger.info("HTTP client closed")


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
        description="Lightweight LAN AI chat gateway for Raspberry Pi",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(LanOnlyMiddleware)

    origins = _cors_origins(cfg)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins else ["http://localhost", "http://127.0.0.1"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(api_v1_router)

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    templates = None
    if TEMPLATES_DIR.is_dir():
        jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
            auto_reload=False,
        )
        templates = Jinja2Templates(env=jinja_env)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/chat", response_class=HTMLResponse, include_in_schema=False)
    async def chat_page(request: Request):
        if templates is None:
            return HTMLResponse(
                "<h1>LocalAI Hub</h1><p>API running. See <a href='/docs'>/docs</a>.</p>",
                status_code=503,
            )
        return templates.TemplateResponse(request=request, name="chat.html", context={})

    return app


app = create_app()
