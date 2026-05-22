from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config.settings import get_settings


def _rate_limit_key(request) -> str:
    return get_remote_address(request)


def _build_default_limits() -> list[str]:
    return [f"{get_settings().rate_limit_per_minute}/minute"]


limiter = Limiter(key_func=_rate_limit_key, default_limits=_build_default_limits())
