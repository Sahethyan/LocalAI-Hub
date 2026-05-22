from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Pi liveness + light system stats."""
    payload: dict = {"status": "ok"}

    try:
        import psutil

        payload["cpu_percent"] = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        payload["memory_mb"] = {
            "used": round(mem.used / (1024 * 1024)),
            "total": round(mem.total / (1024 * 1024)),
        }
    except Exception:
        pass

    return payload
