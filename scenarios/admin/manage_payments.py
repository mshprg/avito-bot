import time

from aiogram import Router, Bot, F, types
from aiogram.enums import ParseMode
from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id
from models.payment import Payment
from models.subscription import Subscription
from models.user import User
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    # Обработчик команды /payments для получения платежей и их состояния
    @router.message(Command("payments"), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def get_confirmations(message: types.Message, state: FSMContext):
        try:
            # Сохраняем ID текущего сообщения и название состояния для последующего использования
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="payments_admin_ids"
            )

            # Открываем сессию для взаимодействия с базой данных
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Получаем все платежи из базы данных
                    result = await session.execute(
                        select(Payment)
                    )
                    payments = result.scalars().all()

                    # Если нет платежей, отправляем уведомление
                    if len(payments) == 0:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Платежей не найдено",
                            keyboard=kb.create_delete_admin_messages_keyboard(),
                            state_name="payments_admin_ids",
                        )
                        return

                    # Получаем пользователей, которые связаны с платежами
                    user_ids = [c.telegram_user_id for c in payments]
                    result = await session.execute(
                        select(User).filter(User.telegram_user_id.in_(user_ids))
                    )
                    users = result.scalars().all()

                    # Создаём словарь для сопоставления ID пользователей с объектами пользователей
                    d = {}
                    for u in users:
                        d[u.telegram_user_id] = u

                    # Отправляем уведомление администратору с инструкцией по обработке платежей
                    await send_state_message(
                        state=state,
                        message=message,
                        text="<b>Внимание!</b>\nОтправляйте сообщение с кнопокой действий только в случае "
                             "необходимости, например если пользователь открыл или закрыл заявку с ошибкой "
                             "и сообщил вам об этом",
                        parse_mode=ParseMode.HTML,
                        keyboard=kb.create_delete_admin_messages_keyboard(),
                        state_name="payments_admin_ids",
                    )

                    # Создаём список видимых платежей с информацией о платёжных действиях
                    visible_payments = []
                    for c in payments:
                        status = "err"
                        # Определяем статус платежа
                        if c.status == 0:
                            status = "успешно"
                        elif c.status == 1:
                            status = "ошибка"
                        elif c.status == 2:
                            status = "ожидает оплаты"
                        elif c.status == 3:
                            status = "возвращён или ожидает возврата"

                        # Получаем информацию о пользователе, связанном с платёжным сообщением
                        u = d[c.telegram_user_id]
                        # Формируем текст сообщения с деталями о платеже
                        text = (
                            f"<b>Перевод от пользовтеля {u.name}</b>\nНомер телефона: {u.phone}\nСумма: <b>{c.amount} "
                            f"</b>\nСтатус: <b>{status}</b>\nНомер счёта: <b>{c.number}</b>")

                        keyboard = None
                        # Если платеж находится в процессе обработки, показываем кнопки для подтверждения
                        if 0 <= c.status <= 2:
                            keyboard = kb.create_list_confirmations_keyboard()

                        # Отправляем сообщение с информацией о платеже и клавишами для действий
                        m = await send_state_message(
                            state=state,
                            message=message,
                            text=text,
                            parse_mode=ParseMode.HTML,
                            keyboard=keyboard,
                            state_name="payments_admin_ids",
                        )
                        # Добавляем в список видимых платежей информацию о сообщении
                        visible_payments.append({
                            'message_id': m.message_id,
                            'payment': c.to_dict()
                        })

                    # Сохраняем список видимых платежей в состояние
                    await state.update_data(visible_payments=visible_payments)

                    # Отправляем сообщение о возможных действиях для администраторов
                    await send_state_message(
                        state=state,
                        message=message,
                        text="Действия",
                        keyboard=kb.create_delete_admin_messages_keyboard(),
                        state_name="payments_admin_ids",
                    )

                # Подтверждаем изменения в базе данных
                await session.commit()

        except Exception as e:
            print(e)

    # Обработчик коллбэка для подтверждения платежа
    @router.callback_query(F.data == callbacks.APPROVED_CONF_CALLBACK, UserFilter(check_admin=True))
    async def approved_confirmation_callback(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            # Открываем сессию для взаимодействия с базой данных
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    pmt = None
                    # Получаем данные состояния для поиска видимых платежей
                    data = await state.get_data()
                    visible_confirmations = data.get("visible_payments", [])

                    # Ищем платёж, соответствующий callback
                    for c in visible_confirmations:
                        if c['message_id'] == callback_query.message.message_id:
                            pmt = c['payment']

                    if pmt is None:
                        return

                    # Получаем платёж из базы данных
                    result = await session.execute(
                        select(Payment).filter(Payment.id == pmt['id'])
                    )
                    payment = result.scalars().first()

                    if payment is None:
                        return

                    # Получаем подписку на тариф
                    result = await session.execute(
                        select(Subscription).filter(
                            and_(
                                Subscription.telegram_user_id == payment.telegram_user_id,
                                Subscription.duration == payment.duration,
                            )
                        )
                    )
                    subscription = result.scalars().first()

                    # Если подписки нет, то создаем новую
                    if subscription is None:
                        subscription = Subscription(
                            telegram_user_id=payment.telegram_user_id,
                            duration=payment.duration,
                            description=payment.description,
                            end_time=int(time.time() * 1000) + 86400000 * 30 * payment.duration
                        )
                        session.add(subscription)
                    else:  # Если подписка есть, то меняем время окончания
                        subscription.end_time = int(time.time() * 1000) + 86400000 * 30 * payment.duration

                    session.add(subscription)

                    # Обновляем статус платежа
                    payment.status = 0

                # Подтверждаем изменения в базе данных
                await session.commit()

        except Exception as e:
            print(e)

    dp.include_router(router)
