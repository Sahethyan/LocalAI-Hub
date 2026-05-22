from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import Chat, Message
from app.schemas.chat import TITLE_MAX_LEN

DEFAULT_CHAT_TITLE = "New chat"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _title_from_message(content: str) -> str:
    text = " ".join(content.strip().split())
    if not text:
        return DEFAULT_CHAT_TITLE
    return text[:TITLE_MAX_LEN]


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_chat(
        self, *, title: str | None = None, model: str | None = None
    ) -> Chat:
        chat = Chat(
            title=title or DEFAULT_CHAT_TITLE,
            model=model,
        )
        self.session.add(chat)
        await self.session.commit()
        await self.session.refresh(chat)
        return chat

    async def list_chats(self, *, limit: int = 50, offset: int = 0) -> list[Chat]:
        stmt = (
            select(Chat)
            .order_by(Chat.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_chat(self, chat_id: int) -> Chat | None:
        return await self.session.get(Chat, chat_id)

    async def get_chat_with_messages(self, chat_id: int) -> Chat | None:
        stmt = (
            select(Chat)
            .where(Chat.id == chat_id)
            .options(selectinload(Chat.messages))
        )
        result = await self.session.execute(stmt)
        chat = result.scalar_one_or_none()
        if chat is not None:
            chat.messages.sort(key=lambda m: m.created_at)
        return chat

    async def delete_chat(self, chat_id: int) -> bool:
        chat = await self.session.get(Chat, chat_id)
        if chat is None:
            return False
        await self.session.delete(chat)
        await self.session.commit()
        return True

    async def get_messages(self, chat_id: int) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_message(self, message_id: int) -> bool:
        message = await self.session.get(Message, message_id)
        if message is None:
            return False
        await self.session.delete(message)
        await self.session.commit()
        return True

    async def append_message(
        self, chat_id: int, role: str, content: str
    ) -> Message | None:
        chat = await self.session.get(Chat, chat_id)
        if chat is None:
            return None

        if role == "user" and chat.title == DEFAULT_CHAT_TITLE:
            chat.title = _title_from_message(content)

        message = Message(chat_id=chat_id, role=role, content=content)
        chat.updated_at = _utcnow()
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message
