from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import load_settings
from app.database.session import create_engine, create_session_factory
from app.handlers.admin import router as admin_router
from app.handlers.booking import router as booking_router
from app.handlers.client import router as client_router
from app.middlewares import DbMiddleware, ErrorMiddleware

logger = logging.getLogger(__name__)


async def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(ErrorMiddleware())
    dp.update.middleware(DbMiddleware(session_factory, settings))
    dp.include_router(admin_router)
    dp.include_router(booking_router)
    dp.include_router(client_router)

    logger.info("Bot started")
    try:
        await dp.start_polling(bot)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
