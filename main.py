import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError

import config
from database.db import init_db
from handlers import setup_routers
from middlewares.subscription import SubscriptionMiddleware
from tasks import setup_scheduled_tasks

_handlers = [logging.StreamHandler()]
try:
    _handlers.append(logging.FileHandler(config.LOG_FILE, encoding="utf-8"))
except OSError:
    pass
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", handlers=_handlers)
logger = logging.getLogger(__name__)


async def main():
    await init_db()
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    router = setup_routers()
    router.message.middleware(SubscriptionMiddleware())
    router.callback_query.middleware(SubscriptionMiddleware())
    dp.include_router(router)

    setup_scheduled_tasks(bot, config.DB_PATH)

    logger.info("Bot starting...")
    try:
        await dp.start_polling(bot)
    except TelegramUnauthorizedError:
        logger.error(
            "Invalid BOT_TOKEN. Check: 1) Token in .env / Render env vars "
            "2) Token from @BotFather 3) No extra spaces or quotes"
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
