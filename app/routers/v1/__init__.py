from fastapi import APIRouter

from app.routers.v1 import generate, health, models, status

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router, tags=["health"])
api_v1_router.include_router(status.router, tags=["status"])
api_v1_router.include_router(models.router, tags=["models"])
api_v1_router.include_router(generate.router, tags=["generate"])
