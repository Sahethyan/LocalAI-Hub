#!/usr/bin/env python3
"""Bootstrap SQLite schema (chats, messages). Run from project root."""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.models.database import init_db  # noqa: E402


async def main() -> None:
    await init_db()
    print("Database tables created (chats, messages, settings).")


if __name__ == "__main__":
    asyncio.run(main())
