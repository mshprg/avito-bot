import datetime
import time

from aiogram import Bot, Router, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import callbacks
import kb
from config import ROOT_USER_IDS
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id
from models.payment import Payment
from models.shop import Shop
from models.subscription import Subscription
from models.user import User
from robokassa.payment import create_payment_link


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(F.text == "Информация о подписке", UserFilter())
    async def subscribe_information(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="subscribe_ids",
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Subscription).filter(Subscription.telegram_user_id == message.from_user.id)
                    )
                    subscription = result.scalars().first()

                    result = await session.execute(
                        select(User).filter(User.telegram_user_id == message.from_user.id)
                    )
                    user = result.scalars().first()

                    result = await session.execute(
                        select(Shop)
                    )
                    shop = result.scalars().first()

                    text = "<b>- - - Информация о подписке - - -</b>\nСтатус: "

                    if subscription.status == 0:
                        text += "<b>активна</b>"
                    elif subscription.status == 1:
                        text += "<b>заморожена</b>"
                    elif subscription.status == 2:
                        text += "<b>неактивна</b>"
                    elif subscription.status == 3:
                        text += "<b>пробный период</b>"
                    else:
                        text += "error"

                    text += "\n"

                    if subscription.end_time > int(time.time() * 1000):
                        unix_time = subscription.end_time / 1000
                        date = datetime.datetime.utcfromtimestamp(unix_time)
                        formatted_date = date.strftime('%d.%m.%Y')

                        text += f"Дата окончания доступа: <b>{formatted_date}</b>\n"

                    if user.admin or user.telegram_user_id in ROOT_USER_IDS:
                        keyboard = kb.create_admin_subscribe_keyboard()
                    else:
                        keyboard = kb.create_pay_subscribe_keyboard()
                        text += f"\nПриобрести 30 дней доступа - {shop.subscribe_30days} руб."

                    await send_state_message(
                        state=state,
                        message=message,
                        text=text,
                        keyboard=keyboard,
                        state_name="subscribe_ids",
                        parse_mode=ParseMode.HTML
                    )

            await send_state_message(
                state=state,
                message=message,
                text="Действия",
                state_name="subscribe_ids",
                keyboard=kb.create_delete_shop_messages()
            )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.BUY_SUBSCRIBE_CALLBACK, UserFilter())
    async def generate_pay_for_user(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(User.telegram_user_id == callback_query.from_user.id)
                    )
                    user = result.scalars().first()

                    result = await session.execute(
                        select(Payment).filter(and_(
                            Payment.telegram_user_id == callback_query.from_user.id,
                            Payment.status == 2,
                        ))
                    )
                    payments = result.scalars().all()

                    result = await session.execute(
                        select(Shop)
                    )
                    shop = result.scalars().first()

                    receipt = {
                        "items": [
                            {
                                "name": "Доступ к заявкам на 30 дней",
                                "quantity": 1,
                                "sum": shop.subscribe_30days,
                                "cost": shop.subscribe_30days,
                                "payment_method": "full_payment",
                                "payment_object": "service",
                                "tax": "none"
                            }
                        ]
                    }

                    link = await create_payment_link(
                        amount=shop.subscribe_30days,
                        phone=user.phone,
                        telegram_user_id=user.telegram_user_id,
                        receipt=receipt,
                    )

                    if len(payments):
                        for p in payments:
                            await session.delete(p)

                    text = f"<b><a href='{link}'>Ссылка на оплату</a>\nПосле оплаты ожидайте сообщение</b>"

                    await send_state_message(
                        state=state,
                        message=callback_query.message,
                        text=text,
                        state_name="subscribe_ids",
                        parse_mode=ParseMode.HTML
                    )

                await session.commit()
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.BUY_ADMIN_SUBSCRIBE_CALLBACK, UserFilter(check_admin=True))
    async def extend_admin_subscribe(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Subscription).filter(Subscription.telegram_user_id == callback_query.from_user.id)
                    )
                    subscription = result.scalars().first()

                    subscription.end_time += 86400000 * 30

                await session.commit()

            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Доступ продлен на 30 дней",
                state_name="subscribe_ids",
                keyboard=kb.create_delete_admin_messages_keyboard()
            )
        except Exception as e:
            print(e)

    dp.include_router(router)
