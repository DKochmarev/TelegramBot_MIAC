import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from config_reader import BOT_TOKEN
from handlers import (common, schedule, booking, allday_booking, admin, calendar_handler, cancellation)
from db.engine import session_maker
from middlewares.db import DbSessionMiddleware
from middlewares.auth import AuthMiddleware


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    dp.update.middleware(DbSessionMiddleware(session_pool=session_maker))
    dp.update.middleware(AuthMiddleware())

    dp.include_router(admin.router)
    dp.include_router(common.router)

    dp.include_router(schedule.router)

    dp.include_router(calendar_handler.router)

    dp.include_router(booking.router)
    dp.include_router(allday_booking.router)
    dp.include_router(cancellation.router)
    # dp.include_router(shared_trips.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
