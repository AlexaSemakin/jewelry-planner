import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from aiogram import Bot
from aiogram.types import Message

logger = logging.getLogger(__name__)
T = TypeVar("T")


async def _with_retries(operation: Callable[[], Awaitable[T]], operation_name: str) -> T | None:
    for attempt in range(1, 4):
        try:
            return await operation()
        except Exception:
            logger.exception("%s failed, attempt %s/3", operation_name, attempt)
            if attempt < 3:
                await asyncio.sleep(30 * 60)
    return None


async def send_message_with_retries(bot: Bot, chat_id: int, text: str, **kwargs: Any) -> Message | None:
    return await _with_retries(lambda: bot.send_message(chat_id, text, **kwargs), "send_message")


async def send_photo_with_retries(bot: Bot, chat_id: int, photo: str, **kwargs: Any) -> Message | None:
    return await _with_retries(lambda: bot.send_photo(chat_id, photo=photo, **kwargs), "send_photo")


async def safe_send_message(bot: Bot, chat_id: int, text: str, **kwargs: Any) -> bool:
    return await send_message_with_retries(bot, chat_id, text, **kwargs) is not None


async def safe_send_photo(bot: Bot, chat_id: int, photo: str, **kwargs: Any) -> bool:
    return await send_photo_with_retries(bot, chat_id, photo, **kwargs) is not None
