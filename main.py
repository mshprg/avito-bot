import asyncio
import logging
from collections import Counter
from asyncio import sleep

import pytz
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.jobstores.base import ConflictingIdError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from models.tariff import Tariff
from models.user import User
from scenarios import handlers, handlers_admin
from scenarios.admin import ban_users, generate_report, manage_admins, manage_cities, manage_tariffs, \
    manage_payments, manage_items, manage_questions_improvements, restart_bot, \
    manage_users, sending
from scenarios.user import create_feedback, finish_application, open_application, registration, stop_application, \
    user_improvements_questions, show_educational_videos, show_tariffs
from db import init_db, AsyncSessionLocal, delete_expired_subscriptions
import config
import avito
from robokassa import payment
from models.city import City

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))


def schedule_jobs():
    import report
    try:
        scheduler.add_job(report.generate_report, 'cron', hour=0, minute=0)
        scheduler.add_job(delete_expired_subscriptions, 'interval', minutes=1)
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
    manage_tariffs.load_handlers(dp, bot)
    manage_payments.load_handlers(dp, bot)
    manage_items.load_handlers(dp, bot)
    manage_questions_improvements.load_handlers(dp, bot)
    manage_users.load_handlers(dp, bot)
    restart_bot.load_handlers(dp, bot)
    sending.load_handlers(dp, bot)

    create_feedback.load_handlers(dp, bot)
    show_educational_videos.load_handlers(dp, bot)
    finish_application.load_handlers(dp, bot)
    open_application.load_handlers(dp, bot)
    registration.load_handlers(dp, bot)
    stop_application.load_handlers(dp, bot)
    user_improvements_questions.load_handlers(dp, bot)
    show_tariffs.load_handlers(dp, bot)

    users = []

    # Стартовые тарифы
    initial_tariffs = [
        {
            'price': 10000,
            'duration': 1,
            'description': ''
        },
        {
            'price': 21000,
            'duration': 3,
            'description': 'Чат с мастерами (канал и группа  "Строитель")'
        },
        {
            'price': 24000,
            'duration': 6,
            'description': 'Чат со мной и мастерами (канал и группа  "Строитель" + канал и группа "Заявка легко")'
        }
    ]

    async with AsyncSessionLocal() as session:
        async with session.begin():
            # Получаем все существующие тарифы из базы
            result = await session.execute(
                select(Tariff)
            )
            tariffs_db = result.scalars().all()

            # Получаем все существующие города из базы
            result = await session.execute(
                select(City)
            )
            cities_db = result.scalars().all()

            # Создаем словарь в котором подсчитано кол-во повторений для каждого duration в
            # массиве словарей tariffs_db
            duration_counts = Counter(tariff.duration for tariff in tariffs_db)

            # Проходимся по всем стартовым тарифам (initial_tariffs)
            for tariff in initial_tariffs:
                count = duration_counts[tariff['duration']]

                # Если тарифа с таким duration ещё нет в базе, то создаем
                if count == 0:
                    new_tariff = Tariff(
                        duration=tariff['duration'],
                        price=tariff['price'],
                        description=tariff['description']
                    )
                    session.add(new_tariff)

            # Если городов нет, то создаем один город
            if len(cities_db) == 0:
                city = City(
                    city="Калининград"
                )
                session.add(city)

            # Получем всех юзеров
            result = await session.execute(
                select(User)
            )
            users_db = result.scalars().all()

            # Переводим каждого юзера в словарь
            for u in users_db:
                users.append(u.to_dict())

        await session.commit()

    # Сообщаем каждому юзеру о том, что бот был перезагружен
    for user in users:
        text = ("<b>Внимание!</b>\nБот был перезагружен, для корректной работы требуется очистить чат и запустить "
                "команду <b>/reload</b>")
        try:
            await sleep(0.6)
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
