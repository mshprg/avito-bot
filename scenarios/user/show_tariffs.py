import datetime
import time

from aiogram import Bot, Router, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_, asc

import callbacks
import kb
from config import ROOT_USER_IDS
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id
from models.payment import Payment
from models.subscription import Subscription
from models.tariff import Tariff
from models.user import User
from robokassa.payment import create_payment_link


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(F.text == "Информация о подписке", UserFilter())
    async def subscribe_information(message: types.Message, state: FSMContext):
        try:
            # Добавляем id соощения в массив subscribe_ids в стейте
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="subscribe_ids",
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Получем все подписки пользователя
                    result = await session.execute(
                        select(Subscription).filter(
                            and_(
                                Subscription.telegram_user_id == message.from_user.id,
                                Subscription.end_time > int(time.time() * 1000)
                            )
                        )
                    )
                    subscriptions = result.scalars().all()

                    # Получем пользователя
                    result = await session.execute(
                        select(User).filter(User.telegram_user_id == message.from_user.id)
                    )
                    user = result.scalars().first()

                    # Получаем все тарифы
                    result = await session.execute(
                        select(Tariff).order_by(asc(Tariff.duration))
                    )
                    tariffs = result.scalars().all()

                    text = "<b>- - - Информация о подписках - - -</b>"

                    await send_state_message(
                        state=state,
                        message=message,
                        text=text,
                        state_name="subscribe_ids",
                        parse_mode=ParseMode.HTML
                    )

                    # Выводим все подписки пользователя
                    for subscription in subscriptions:
                        text = f"<b>Длительность (месяцы):</b> {subscription.duration}\n"
                        text += f"<b>Описание:</b> {subscription.description}\n"

                        # Переводим время в дату
                        unix_time = subscription.end_time / 1000
                        date = datetime.datetime.utcfromtimestamp(unix_time)
                        formatted_date = date.strftime('%d.%m.%Y')

                        text += f"<b>Дата окончания:</b> {formatted_date}"

                        await send_state_message(
                            state=state,
                            message=message,
                            text=text,
                            state_name="subscribe_ids",
                            parse_mode=ParseMode.HTML
                        )

                    text = "<b>- - - Доступные тарифы - - -</b>"

                    await send_state_message(
                        state=state,
                        message=message,
                        text=text,
                        state_name="subscribe_ids",
                        parse_mode=ParseMode.HTML
                    )

                    # Массив тарифов в виде словарей
                    visible_tariffs = []

                    # Генерируем клавиатуру
                    if user.telegram_user_id in ROOT_USER_IDS:
                        keyboard = kb.create_admin_subscribe_keyboard()
                    else:
                        keyboard = kb.create_pay_subscribe_keyboard()

                    # Выводим все доступные тарифы
                    for tariff in tariffs:
                        text = f"<b>Длительность (месяцы):</b> {tariff.duration}\n"
                        text += f"<b>Описание:</b> {tariff.description}\n"
                        text += f"<b>Цена:</b> {tariff.price} руб."

                        if tariff.duration > 1:
                            text += f"\n<b>Стоимость месяца:</b> {round(tariff.price / tariff.duration)} руб."

                        m = await send_state_message(
                            state=state,
                            message=message,
                            text=text,
                            keyboard=keyboard,
                            state_name="subscribe_ids",
                            parse_mode=ParseMode.HTML
                        )

                        visible_tariffs.append({
                            'message_id': m.message_id,
                            'tariff': tariff.to_dict(),
                        })

                    # Сохраняем массив соответствий message_id и tariff в стейт
                    await state.update_data(visible_tariffs=visible_tariffs)

            await send_state_message(
                state=state,
                message=message,
                text="Действия",
                state_name="subscribe_ids",
                keyboard=kb.create_delete_shop_messages()
            )
        except Exception as e:
            print(e)

    # Обработка кнопки "Купить" для обычного пользователя
    @router.callback_query(F.data == callbacks.BUY_SUBSCRIBE_CALLBACK, UserFilter())
    async def generate_pay_for_user(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Получаем пользователя
                    result = await session.execute(
                        select(User).filter(User.telegram_user_id == callback_query.from_user.id)
                    )
                    user = result.scalars().first()

                    # Получем все незавершенные оплаты для данного пользователя
                    result = await session.execute(
                        select(Payment).filter(and_(
                            Payment.telegram_user_id == callback_query.from_user.id,
                            Payment.status == 2,
                        ))
                    )
                    payments = result.scalars().all()

                    # Из стейта получаем visible_tariffs
                    data = await state.get_data()

                    visible_tariffs = data.get('visible_tariffs')

                    # Находим словарь с указанным message_id
                    tariff_state = next((tariff for tariff in visible_tariffs if
                                         tariff["message_id"] == callback_query.message.message_id), None)

                    # Получаем все тарифы
                    result = await session.execute(
                        select(Tariff).order_by(asc(Tariff.duration))
                    )
                    tariffs = result.scalars().all()

                    # Получаем тариф с нужной длительностью из бд
                    tariff = next((tariff for tariff in tariffs if tariff.duration == tariff_state['tariff']['duration']), None)

                    # Получем все подписки пользователя
                    result = await session.execute(
                        select(Subscription).filter(
                            and_(
                                Subscription.telegram_user_id == callback_query.from_user.id,
                                Subscription.end_time > int(time.time() * 1000)
                            )
                        )
                    )
                    subscriptions = result.scalars().all()

                    # Если нет такого тарифа в бд, то выходим
                    if not tariff:
                        return

                    # Если у пользователя есть активная подписка, то выходим
                    if len(subscriptions) > 0:
                        await send_state_message(
                            state=state,
                            message=callback_query.message,
                            text='У вас уже есть активная подписка, дождитесь её завершения',
                            state_name='subscribe_ids'
                        )
                        return

                    tariff_dict = tariff.to_dict()

                    # Подбираем окончание
                    lst_text = 'ев'
                    lst_number = int(str(tariff_dict['duration'])[-1])

                    if lst_number == 1:
                        lst_text = ''
                    elif 1 < lst_number <= 4:
                        lst_text = 'а'

                    # Создаем чек
                    receipt = {
                        "items": [
                            {
                                "name": f"Оплата подписки на {tariff_dict['duration']} месяц{lst_text}",
                                "quantity": 1,
                                "sum": tariff_dict['price'],
                                "cost": tariff_dict['price'],
                                "payment_method": "full_payment",
                                "payment_object": "service",
                                "tax": "none"
                            }
                        ]
                    }

                    # Создаем ссылку на оплату в робокассе
                    link = await create_payment_link(
                        amount=tariff_dict['price'],
                        phone=user.phone,
                        telegram_user_id=user.telegram_user_id,
                        receipt=receipt,
                        duration=tariff_dict['duration'],
                        description=tariff_dict['description']
                    )

                    # Удаляем все ожидающие платежи пользователя
                    if len(payments):
                        for p in payments:
                            await session.delete(p)

                    # Текст сообщения со ссылкой
                    text = (f"<b><a href='{link}'>Ссылка на оплату</a>\nДлительность (месяцев): "
                            f"{tariff_dict['duration']}\nПосле оплаты ожидайте сообщение</b>")

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

    # Обработка кнопки "Купить" для администратора
    @router.callback_query(F.data == callbacks.BUY_ADMIN_SUBSCRIBE_CALLBACK, UserFilter(check_admin=True))
    async def extend_admin_subscribe(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Из стейта получаем visible_tariffs
                    data = await state.get_data()

                    visible_tariffs = data.get('visible_tariffs')

                    # Находим словарь с указанным message_id
                    tariff = next((tariff for tariff in visible_tariffs if
                                   tariff["message_id"] == callback_query.message.message_id), None)

                    # Если нет такого соответствия, то выходим
                    if not tariff:
                        return

                    # Получаем все подписки админа с такой же длительностью
                    result = await session.execute(
                        select(Subscription).filter(and_(
                            Subscription.telegram_user_id == callback_query.from_user.id,
                            Subscription.duration == tariff['tariff']['duration'],
                        )
                        )
                    )
                    subscription = result.scalars().first()

                    # Если у админа уже есть подписка на выбранный тариф, то выходим
                    if subscription:
                        return

                    # Создаем новую подписку для админа
                    subscription = Subscription(
                        telegram_user_id=callback_query.from_user.id,
                        duration=tariff['tariff']['duration'],
                        description=tariff['tariff']['description'],
                        end_time=int(time.time() * 1000) + 86400000 * 30 * tariff['tariff']['duration'],
                    )

                    session.add(subscription)

                await session.commit()

            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Доступ продлен",
                state_name="subscribe_ids",
                keyboard=kb.create_delete_admin_messages_keyboard()
            )
        except Exception as e:
            print(e)

    dp.include_router(router)
