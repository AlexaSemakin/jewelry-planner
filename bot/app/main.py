import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from app.config import settings
from app.db import init_db
from app.handlers import router
from app.scheduler import setup_scheduler


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(settings.log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8"),
        ],
    )


def create_telegram_session() -> AiohttpSession:
    proxy_url = os.getenv("PROXY_URL") or settings.proxy_url
    if proxy_url:
        return AiohttpSession(proxy=proxy_url)
    return AiohttpSession()


async def main() -> None:
    setup_logging()
    await init_db()

    bot = Bot(
        token=settings.bot_token,
        session=create_telegram_session(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    scheduler = setup_scheduler(bot)
    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
