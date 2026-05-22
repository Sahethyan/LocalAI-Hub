from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import async_session_factory
from app.schemas.settings import HubSettingsResponse, HubSettingsUpdate
from app.services.settings_service import get_settings_response, update_settings

router = APIRouter(prefix="/settings", tags=["settings"])


async def get_db_session():
    async with async_session_factory() as session:
        yield session


@router.get("", response_model=HubSettingsResponse)
async def read_settings(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HubSettingsResponse:
    return await get_settings_response(session, request.app)


@router.post("", response_model=HubSettingsResponse)
async def save_settings(
    body: HubSettingsUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HubSettingsResponse:
    return await update_settings(session, request.app, body)
