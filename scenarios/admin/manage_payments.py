from aiogram import Router, Bot, F, types
from aiogram.enums import ParseMode
from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id
from models.payment import Payment
from models.user import User
from models.work import Work
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(Command("payments"), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def get_confirmations(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="payments_admin_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Payment)
                    )
                    payments = result.scalars().all()

                    if len(payments) == 0:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Платежей не найдено",
                            keyboard=kb.create_delete_admin_messages_keyboard(),
                            state_name="payments_admin_ids",
                        )
                        return

                    user_ids = [c.telegram_user_id for c in payments]
                    result = await session.execute(
                        select(User).filter(User.telegram_user_id.in_(user_ids))
                    )
                    users = result.scalars().all()
                    d = {}

                    for u in users:
                        d[u.telegram_user_id] = u

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

                    visible_payments = []
                    for c in payments:
                        status = "err"
                        action = "err"
                        if c.status == 0:
                            status = "успешно"
                        elif c.status == 1:
                            status = "ошибка"
                        elif c.status == 2:
                            status = "ожидает оплаты"
                        elif c.status == 3:
                            status = "возвращён или ожидает возврата"
                        if c.action == "open":
                            action = "открытие заявки"
                        elif c.action == "close":
                            action = "закрытие заявки"
                        u = d[c.telegram_user_id]
                        text = (f"<b>Перевод от пользовтеля {u.name}</b>\nНомер телефона: {u.phone}\nСумма: <b>{c.amount}"
                                f"</b>\nСтатус: <b>{status}</b>\nНомер счёта: <b>{c.number}</b>\nДействие: <b>{action}</b>")
                        keyboard = None
                        if 0 <= c.status <= 2:
                            keyboard = kb.create_list_confirmations_keyboard()
                        m = await send_state_message(
                            state=state,
                            message=message,
                            text=text,
                            parse_mode=ParseMode.HTML,
                            keyboard=keyboard,
                            state_name="payments_admin_ids",
                        )
                        visible_payments.append({
                            'message_id': m.message_id,
                            'payment': c.to_dict()
                        })

                    await state.update_data(visible_payments=visible_payments)

                    await send_state_message(
                        state=state,
                        message=message,
                        text="Действия",
                        keyboard=kb.create_delete_admin_messages_keyboard(),
                        state_name="payments_admin_ids",
                    )

                await session.commit()

        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.APPROVED_CONF_CALLBACK, UserFilter(check_admin=True))
    async def approved_confirmation_callback(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    pmt = None
                    data = await state.get_data()
                    visible_confirmations = data.get("visible_payments", [])

                    for c in visible_confirmations:
                        if c['message_id'] == callback_query.message.message_id:
                            pmt = c['payment']

                    if pmt is None:
                        return

                    result = await session.execute(
                        select(Payment).filter(Payment.id == pmt['id'])
                    )
                    payment = result.scalars().first()

                    if payment is None:
                        return

                    if payment.status > 2:
                        return

                    result = await session.execute(
                        select(Work).filter(Work.telegram_user_id == payment.telegram_user_id)
                    )
                    work = result.scalars().first()

                    if work:
                        if work.application_id != payment.application_id:
                            await send_state_message(
                                state=state,
                                message=callback_query.message,
                                text="Этот перевод относится к заявке, отличой от той, над которой работает "
                                     "пользователь который произвёл оплату",
                                parse_mode=ParseMode.HTML,
                                keyboard=kb.create_delete_admin_messages_keyboard(),
                                state_name="payments_admin_ids",
                            )
                            return

                    keyboard = None
                    text = "<b>!НЕ УДАЛЯЙТЕ ЭТО СООБЩЕНИЕ!</b>\nОплата подтверждена"
                    if payment.action == "open":
                        keyboard = kb.create_confirmation_keyboard()
                    elif payment.action == "close":
                        keyboard = kb.create_close_application_keyboard()

                    if keyboard:
                        try:
                            await bot.edit_message_text(
                                chat_id=payment.telegram_user_id,
                                message_id=payment.telegram_message_id,
                                text=text,
                                parse_mode=ParseMode.HTML,
                                reply_markup=keyboard
                            )
                        except Exception as e:
                            print(e)
                            await bot.send_message(
                                chat_id=payment.telegram_user_id,
                                text=text,
                                reply_markup=keyboard,
                                parse_mode=ParseMode.HTML,
                            )

                    payment.status = 0

                await session.commit()
        except Exception as e:
            print(e)

    dp.include_router(router)
