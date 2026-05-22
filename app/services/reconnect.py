import asyncio
import logging
from datetime import datetime, timezone

from app.schemas.ollama import OllamaConnectionStatus
from app.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OllamaReconnectMonitor:
    """Background poller: online | offline | degraded + last successful ping."""

    def __init__(
        self,
        ollama: OllamaClient,
        *,
        interval_seconds: float = 10.0,
        degraded_after_failures: int = 2,
    ) -> None:
        self._ollama = ollama
        self._interval = interval_seconds
        self._degraded_after = degraded_after_failures
        self._task: asyncio.Task | None = None
        self._consecutive_failures = 0
        self.status: OllamaConnectionStatus = "offline"
        self.last_success_at: datetime | None = None
        self.last_check_at: datetime | None = None
        self.last_message: str | None = None

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run(), name="ollama-reconnect-monitor")
        logger.info("Ollama reconnect monitor started (interval=%ss)", self._interval)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("Ollama reconnect monitor stopped")

    async def _run(self) -> None:
        while True:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unexpected error in Ollama reconnect poll")
            await asyncio.sleep(self._interval)

    async def _poll_once(self) -> None:
        self.last_check_at = _utcnow()
        ok = await self._ollama.health_check()
        if ok:
            self._consecutive_failures = 0
            self.status = "online"
            self.last_success_at = self.last_check_at
            self.last_message = None
            return

        self._consecutive_failures += 1
        if self.last_success_at is None:
            self.status = "offline"
            self.last_message = "Ollama is unreachable on the LAN."
        elif self._consecutive_failures >= self._degraded_after:
            self.status = "degraded"
            self.last_message = "Ollama was reachable but is now failing health checks."
        else:
            self.status = "offline"
            self.last_message = "Ollama is unreachable on the LAN."

    def snapshot(self) -> dict:
        return {
            "status": self.status,
            "last_success_at": self.last_success_at,
            "last_check_at": self.last_check_at,
            "message": self.last_message,
        }
