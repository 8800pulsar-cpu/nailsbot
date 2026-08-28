from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.services.master_service import MasterNotConfiguredError, MasterService

logger = logging.getLogger(__name__)

USER_ERROR = "Произошла ошибка. Попробуйте ещё раз."
MASTER_ERROR = (
    "Бот ещё не настроен. Администратору нужно создать мастера "
    "(python -m app.bootstrap) и при необходимости указать MASTER_ID в .env."
)


class DbMiddleware(BaseMiddleware):
    def __init__(self, session_factory: async_sessionmaker, settings: Settings) -> None:
        self.session_factory = session_factory
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.session_factory() as session:
            data["session"] = session
            data["settings"] = self.settings
            try:
                master_service = MasterService(session, self.settings)
                data["master"] = await master_service.get_current()
            except MasterNotConfiguredError:
                data["master"] = None
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise


class ErrorMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception:
            logger.exception("Unhandled error while processing update")
            bot = data.get("bot")
            if bot is None:
                return None
            chat_id = _chat_id(event)
            if chat_id is not None:
                await bot.send_message(chat_id, USER_ERROR)
            return None


def _chat_id(event: TelegramObject) -> int | None:
    message = getattr(event, "message", None)
    if message is not None and getattr(message, "chat", None) is not None:
        return message.chat.id
    callback = getattr(event, "callback_query", None)
    if callback is not None and callback.message is not None:
        return callback.message.chat.id
    return getattr(getattr(event, "chat", None), "id", None)
