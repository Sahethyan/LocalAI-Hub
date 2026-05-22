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

    ollama_base_url: str = "http://192.168.1.100:11434"
    ollama_cache_ttl_seconds: int = 45
    ollama_health_timeout_seconds: float = 3.0

    host: str = "0.0.0.0"
    port: int = 8080

    lan_only: bool = True
    allowed_subnets: str = "192.168.0.0/16,10.0.0.0/8,172.16.0.0/12"
    trust_proxy_headers: bool = False

    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    cors_origins: str = ""

    @property
    def allowed_subnet_list(self) -> List[str]:
        return [s.strip() for s in self.allowed_subnets.split(",") if s.strip()]

    @property
    def cors_origin_list(self) -> List[str]:
        if not self.cors_origins.strip():
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
