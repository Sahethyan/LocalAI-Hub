from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Ollama (laptop on LAN)
    ollama_base_url: str = "http://192.168.1.100:11434"
    ollama_cache_ttl_seconds: int = 45
    ollama_health_timeout_seconds: float = 3.0
    ollama_reconnect_interval_seconds: int = 10

    # Server bind
    host: str = "0.0.0.0"
    port: int = 8080
    bind: str = "0.0.0.0"

    # Database
    database_url: str = "sqlite+aiosqlite:///./database/localai.db"

    # LAN security
    lan_only: bool = True
    allowed_subnets: str = "192.168.0.0/16,10.0.0.0/8,172.16.0.0/12"
    # Only trust X-Forwarded-For when behind a known reverse proxy (nginx, etc.)
    trust_proxy_headers: bool = False

    # Optional auth
    basic_auth_user: str | None = None
    basic_auth_password: str | None = None
    api_key: str | None = None

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    # Chat context sent to Ollama (last N messages in thread)
    chat_context_messages: int = 40

    # Rate limiting
    rate_limit_per_minute: int = 60

    # CORS (comma-separated origins; empty = defaults in main.py)
    cors_origins: str = ""

    @property
    def allowed_subnet_list(self) -> List[str]:
        return [s.strip() for s in self.allowed_subnets.split(",") if s.strip()]

    @property
    def cors_origin_list(self) -> List[str]:
        if not self.cors_origins.strip():
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def database_path(self) -> Path:
        """Resolve SQLite file path for mkdir side effects."""
        url = self.database_url
        if url.startswith("sqlite+aiosqlite:///"):
            rel = url.removeprefix("sqlite+aiosqlite:///")
            if rel.startswith("./"):
                return PROJECT_ROOT / rel[2:]
            return Path(rel)
        return PROJECT_ROOT / "database" / "localai.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
