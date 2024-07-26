import asyncio
import logging

import pytz
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.jobstores.base import ConflictingIdError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
import handlers
import handlers_admin
from db import init_db, AsyncSessionLocal
import config
import avito
from models.city import City
from models.comission import Commission
from models.requisites import Requisites

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))


def schedule_jobs():
    import report
    try:
        scheduler.add_job(report.generate_report, 'cron', hour=0, minute=0)
        logger.info("Scheduled jobs")
        scheduler.start()
        logger.info("Scheduler started")
    except ConflictingIdError:
        logger.error("Job with the same ID already exists.")


async def start_bot():
    await init_db()

    await bot.delete_webhook(drop_pending_updates=True)

    handlers_admin.load_handlers_admin(dp, bot)
    handlers.load_handlers(dp, bot)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(Commission)
            )
            commission_db = result.scalars().all()

            result = await session.execute(
                select(Requisites)
            )
            requisites_db = result.scalars().all()

            result = await session.execute(
                select(City)
            )
            cities_db = result.scalars().all()

            if len(commission_db) == 0:
                commission = Commission(
                    fixed=0,
                    percent=0,
                )
                session.add(commission)

            if len(requisites_db) == 0:
                requisites = Requisites(
                    card_number="0000 0000 0000 0000"
                )
                session.add(requisites)

            if len(cities_db) == 0:
                city = City(
                    city="Калининград"
                )
                session.add(city)

        await session.commit()

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


async def main():
    schedule_jobs()

    await asyncio.gather(
        avito.start_avito_webhook(avito.handle_webhook_message),
        start_bot()
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
