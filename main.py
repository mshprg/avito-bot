import asyncio
import logging
from time import sleep

import pytz
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.jobstores.base import ConflictingIdError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from models.user import User
from scenarios import handlers, handlers_admin
from scenarios.admin import ban_users, generate_report, manage_admins, manage_cities, manage_commission, \
    manage_payments, manage_items, manage_questions_improvements, manage_requisites, \
    manage_users
from scenarios.user import create_feedback, finish_application, open_application, registration, stop_application, \
    user_improvements_questions, show_educational_videos
from db import init_db, AsyncSessionLocal
import config
import avito
from robokassa import payment
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

    ban_users.load_handlers(dp, bot)
    generate_report.load_handlers(dp, bot)
    manage_admins.load_handlers(dp, bot)
    manage_cities.load_handlers(dp, bot)
    manage_commission.load_handlers(dp, bot)
    manage_payments.load_handlers(dp, bot)
    manage_items.load_handlers(dp, bot)
    manage_questions_improvements.load_handlers(dp, bot)
    manage_requisites.load_handlers(dp, bot)
    manage_users.load_handlers(dp, bot)

    create_feedback.load_handlers(dp, bot)
    show_educational_videos.load_handlers(dp, bot)
    finish_application.load_handlers(dp, bot)
    open_application.load_handlers(dp, bot)
    registration.load_handlers(dp, bot)
    stop_application.load_handlers(dp, bot)
    user_improvements_questions.load_handlers(dp, bot)

    users = []

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

            result = await session.execute(
                select(User)
            )
            users_db = result.scalars().all()

            for u in users_db:
                users.append(u.to_dict())

        await session.commit()

    for user in users:
        text = ("<b>Внимание!</b>\nБот был перезагружен, для корректной работы требуется очистить чат и запустить "
                "команду <b>/reload</b>")
        try:
            sleep(1)
            await bot.send_message(
                chat_id=user['telegram_chat_id'],
                text=text,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print("Send restart message:", e)

    print("| - - - - - Starting - - - - - |")

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


async def main():
    schedule_jobs()

    await asyncio.gather(
        avito.start_avito_webhook(avito.handle_webhook_message, payment.check_status_payment),
        start_bot()
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
