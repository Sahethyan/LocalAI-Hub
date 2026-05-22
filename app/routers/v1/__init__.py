from fastapi import APIRouter

from app.routers.v1 import chats, health

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router, tags=["health"])
api_v1_router.include_router(chats.router, tags=["chats"])
