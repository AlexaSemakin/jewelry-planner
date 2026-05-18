import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.handlers import router
from app.seed import seed_demo_data


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    settings = get_settings()
    await init_db()

    async with SessionLocal() as session:
        await seed_demo_data(session)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
