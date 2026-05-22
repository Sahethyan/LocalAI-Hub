from fastapi import APIRouter

from app.utils.rate_limit import limiter

router = APIRouter()


@router.get("/health")
@limiter.exempt
async def health() -> dict:
    """Liveness check for monitoring and Phase 1 verification."""
    return {"status": "ok"}
