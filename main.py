# -*- coding: utf-8 -*-

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from bot import monitoring
from bot.database import init_db
from bot.handlers import (
    admin,
    donate,
    language,
    post,
    saved_posts,
    start,
)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not BOT_TOKEN:
        raise SystemExit(
            "Set BOT_TOKEN in config.py or environment."
        )

    # Initialize PostgreSQL database.
    init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )

    dp = Dispatcher()

    dp.update.outer_middleware(
        monitoring.ActivityMiddleware()
    )

    dp.include_router(monitoring.router)
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(language.router)
    dp.include_router(donate.router)
    dp.include_router(post.router)
    dp.include_router(saved_posts.router)

    monitoring.set_started()

    try:
        await bot.delete_webhook(
            drop_pending_updates=True
        )
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
