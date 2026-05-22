import ipaddress
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

# Paths that skip LAN checks (health for local monitoring, static assets)
LAN_EXEMPT_PREFIXES = (
    "/api/v1/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static",
)


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def is_ip_allowed(ip_str: str, subnets: list[str]) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if addr.is_loopback:
        return True
    for cidr in subnets:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            logger.warning("Invalid CIDR in ALLOWED_SUBNETS: %s", cidr)
            continue
        if addr in network:
            return True
    return False


class LanOnlyMiddleware(BaseHTTPMiddleware):
    """Reject requests from IPs outside configured private subnets when LAN_ONLY is enabled."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        cfg = get_settings()
        if not cfg.lan_only:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(prefix) for prefix in LAN_EXEMPT_PREFIXES):
            return await call_next(request)

        client_ip = _client_ip(request)
        if client_ip is None:
            return Response(status_code=403, content="Forbidden: unknown client")

        if not is_ip_allowed(client_ip, cfg.allowed_subnet_list):
            logger.warning("LAN-only reject: %s -> %s", client_ip, path)
            return Response(
                status_code=403,
                content=f"Forbidden: {client_ip} not in allowed subnets",
            )

        return await call_next(request)
