import random
import time
from asyncio import sleep

from aiogram.enums import ParseMode
from sqlalchemy import select, and_

from models.payment import Payment
from models.subscription import Subscription
from models.user import User
from robokassa.robokassa_api import result_payment, generate_payment_link
import config
from aiohttp import web
from db import AsyncSessionLocal


handled_operations = []


# Создание ссылки на оплату
async def create_payment_link(receipt, amount, phone, duration, description, telegram_user_id):
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():

                # Генерируем номер
                number = await generate_unique_number(session)

                phone.replace("+", "")

                # Создаем ссылку
                payment_link = generate_payment_link(
                    merchant_login=config.MERCHANT_LOGIN,
                    merchant_password_1=config.MERCHANT_PASSWORD_1,
                    cost=amount,
                    number=number,
                    description=phone.replace("+", ""),
                    receipt=receipt,
                    is_test=0
                )

                # Создаем платеж в бд со статусом ожидания
                payment = Payment(
                    telegram_user_id=telegram_user_id,
                    amount=amount,
                    created=int(time.time() * 1000),
                    number=number,
                    status=2,
                    duration=duration,
                    description=description,
                )

                session.add(payment)

            await session.commit()

        return payment_link
    except Exception as e:
        print(e)

    return None


# Функция обработки результата платежа, данные приходят из робокассы через вебхук
async def check_status_payment(request):
    from main import bot
    try:
        # Проверяем подпись
        res = await result_payment(config.MERCHANT_PASSWORD_2, request)
        if res == "bad sign":
            print("error - - - - - - - -- - - - \n-\n-\n-\n-\n")
            return
        # Получаем номер платежа
        number = int(res.replace("OK", ""))
        # Проверяем есть ли такой платеж в массиве обработанных,
        # проверяем для того чтобы дважды не обработать один и тот же платеж
        if number in handled_operations:
            return
        else:
            handled_operations.append(number)
        async with (AsyncSessionLocal() as session):
            async with session.begin():
                # Получаем платеж
                result = await session.execute(
                    select(Payment).filter(Payment.number == number)
                )
                payment = result.scalars().first()

                # Получаем юзера
                result = await session.execute(
                    select(User).filter(User.telegram_user_id == payment.telegram_user_id)
                )
                user = result.scalars().first()

                subscription = Subscription(
                    telegram_user_id=payment.telegram_user_id,
                    end_time=int(time.time() * 1000) + 86400000 * 30 * payment.duration,
                    duration=payment.duration,
                    description=payment.description,
                )
                session.add(subscription)

                # Меняем статус платежа на успешно
                payment.status = 0

                # Получаем всех админов
                result = await session.execute(
                    select(User).filter(
                        and_(
                            User.admin == True,
                            User.telegram_user_id.in_(config.ROOT_USER_IDS),
                        )
                    )
                )
                admins = result.scalars().all()

                # Переводим всё в словари
                admins_dict = []
                for admin in admins:
                    admins_dict.append(admin.to_dict())

                admin_text = (f"Пользователь <b>{user.name}</b> приобрёл тариф\n"
                              f"<b>Длительность (месяцев):</b> {payment.duration}\n"
                              f"<b>Описание:</b> {payment.description}\n"
                              f"<b>Сумма оплаты:</b> {payment.amount} руб.\n"
                              f"<b>Номер телефона:</b> {user.phone}")

                payment_dict = payment.to_dict()

            await session.commit()

        # Отправляем пользователю сообщение
        await bot.send_message(
            chat_id=payment_dict['telegram_user_id'],
            text="Доступ предоставлен"
        )

        # Сообщаем админам о том что пользователь приобрёл подписку на тариф
        for admin in admins_dict:
            try:
                await sleep(0.5)
                await bot.send_message(
                    chat_id=admin['telegram_chat_id'],
                    text=admin_text,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                await sleep(1)
                print(e)

        return web.json_response({"ok": True})
    except Exception as e:
        print("Status payment error:", e)
        return web.json_response({"ok": False})


# Генерация случайного числа
async def generate_unique_number(session):
    while True:
        # Генерируем случайное семизначное число с ведущими нулями
        random_number = random.randint(0, 9999999)

        # Проверяем, существует ли оно в базе данных
        exists = (await session.execute(
            select(Payment).filter(Payment.number == random_number)
        )).scalars().first()

        if not exists:
            return random_number
