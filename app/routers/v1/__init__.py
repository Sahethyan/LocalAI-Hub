from fastapi import APIRouter

from app.routers.v1 import chats, health, models, ollama, settings_api

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router, tags=["health"])
api_v1_router.include_router(chats.router, tags=["chats"])
api_v1_router.include_router(models.router, tags=["models"])
api_v1_router.include_router(ollama.router, tags=["ollama"])
api_v1_router.include_router(settings_api.router)
