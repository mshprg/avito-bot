from time import sleep

from aiogram import Router, Bot, types, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from models.addiction import Addiction
from models.application import Application
from models.comission import Commission
from models.payment import Payment
from models.user import User
from models.work import Work
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()
    from applications import show_messages_for_application

    @router.callback_query(F.data == callbacks.TAKE_APPLICATION_CALLBACK, UserFilter())
    async def select_application(callback_query: types.CallbackQuery):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_message_id == callback_query.message.message_id)
                    )
                    addiction = result.scalars().first()

                    if addiction is None:
                        await bot.delete_messages(
                            chat_id=callback_query.message.chat.id,
                            message_ids=[callback_query.message.message_id],
                        )
                        return

                    result = await session.execute(
                        select(Application).filter(
                            Application.id == addiction.application_id)
                    )
                    application = result.scalars().first()

                    if application is None or application.in_working:
                        await bot.send_message(
                            text="Данную зявку уже взяли",
                            chat_id=callback_query.message.chat.id
                        )
                        return

                    result = await session.execute(
                        select(Commission)
                    )
                    commission = result.scalars().first()

                    text = (
                        "*Выберите способ оплаты комиссии:*\n_Фиксированная комиссия_ \- платите сразу\n_Процент от "
                        "стоимости_ \- платите процент от стоимости заказа")

                    await bot.edit_message_text(
                        text=text,
                        chat_id=callback_query.message.chat.id,
                        message_id=callback_query.message.message_id,
                        reply_markup=kb.create_price_keyboard(commission.percent, commission.fixed),
                        parse_mode=ParseMode.MARKDOWN_V2,
                    )

        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.SELECT_FIXED_CALLBACK, UserFilter())
    async def wait_paid(callback_query: types.CallbackQuery, state: FSMContext):
        from robokassa.payment import create_payment_link
        from applications import delete_messages_for_application, delete_applications_for_user
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_message_id == callback_query.message.message_id)
                    )
                    addiction = result.scalars().first()

                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == callback_query.from_user.id)
                    )
                    user = result.scalars().first()

                    if addiction is None:
                        await bot.delete_messages(
                            chat_id=callback_query.message.chat.id,
                            message_ids=[callback_query.message.message_id],
                        )

                    result = await session.execute(
                        select(Application).filter(
                            Application.id == addiction.application_id)
                    )
                    application = result.scalars().first()

                    if application is None or application.in_working or application.waiting_confirmation:
                        await bot.send_message(
                            text="Данную зявку уже взяли",
                            chat_id=callback_query.message.chat.id
                        )
                        return

                    result = await session.execute(
                        select(Commission)
                    )
                    commission = result.scalars().first()

                    await delete_messages_for_application(
                        session, bot, application.id, skip_user_ids=[user.telegram_user_id])

                    await session.flush()

                    await delete_applications_for_user(
                        session=session,
                        bot=bot,
                        telegram_chat_id=user.telegram_chat_id,
                        skip_ids=[application.id]
                    )

                    link = await create_payment_link(
                        amount=commission.fixed,
                        phone=user.phone,
                        application_id=application.id,
                        telegram_user_id=user.telegram_user_id,
                        telegram_message_id=callback_query.message.message_id,
                        type_payment="admin" if user.admin else "fixed",
                        type_action="open",
                    )

                    text = (f"<b>!НЕ УДАЛЯЙТЕ ЭТО СООБЩЕНИЕ!</b>\nВы можете оплатить комиссию, перейдя по "
                            f"<a href='{link}'>ссылке</a>\nПосле оплаты заявка станет доступна")

                    await bot.edit_message_text(
                        text=text,
                        chat_id=callback_query.message.chat.id,
                        message_id=callback_query.message.message_id,
                        parse_mode=ParseMode.HTML,
                        reply_markup=kb.create_back_to_apps_keyboard()
                    )

                await session.commit()

        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.OPEN_APPLICATION_CALLBACK, UserFilter())
    async def set_application(callback_query: types.CallbackQuery, state: FSMContext):
        from applications import delete_messages_for_application, delete_applications_for_user
        try:
            u, a = None, None
            async with AsyncSessionLocal() as session:
                async with session.begin():

                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_message_id == callback_query.message.message_id)
                    )
                    addiction = result.scalars().first()

                    if addiction is None:
                        await bot.delete_messages(
                            chat_id=callback_query.message.chat.id,
                            message_ids=[callback_query.message.message_id],
                        )

                    result = await session.execute(
                        select(Application).filter(
                            Application.id == addiction.application_id)
                    )
                    application = result.scalars().first()

                    result = await session.execute(
                        select(Payment).filter(and_(
                            Payment.application_id == application.id,
                            Payment.action == "open",
                            Payment.telegram_user_id == callback_query.from_user.id,
                        ))
                    )
                    payment = result.scalars().first()

                    pay_type = ""
                    if payment:
                        pay_type = payment.type
                    else:
                        pay_type = "percent"

                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == callback_query.from_user.id)
                    )
                    user = result.scalars().first()

                    result = await session.execute(
                        select(Commission)
                    )
                    commission = result.scalars().first()

                    if user is None:
                        return

                    if user.admin:
                        pay_type = "admin"

                    if application is None or application.in_working:
                        await bot.send_message(
                            text="Данную зявку уже взяли",
                            chat_id=callback_query.message.chat.id
                        )
                        return

                    user.in_working = True
                    user.in_waiting = False

                    application.waiting_confirmation = False
                    application.in_working = True
                    application.working_user_id = callback_query.from_user.id
                    application.pay_type = pay_type
                    if pay_type == "percent":
                        application.com_value = commission.percent
                    elif pay_type == "fixed":
                        application.com_value = commission.fixed

                    work = Work(
                        application_id=application.id,
                        telegram_user_id=user.telegram_user_id
                    )

                    session.add(work)

                    try:
                        await bot.delete_message(
                            chat_id=user.telegram_chat_id,
                            message_id=callback_query.message.id
                        )
                    except Exception as e:
                        pass

                    await delete_messages_for_application(session, bot, application.id)

                    await session.flush()

                    await delete_applications_for_user(session, bot, user.telegram_chat_id)

                    u = {'telegram_chat_id': user.telegram_chat_id}
                    a = {
                        'avito_chat_id': application.avito_chat_id,
                        'user_id': application.user_id,
                        'author_id': application.author_id,
                        'username': application.username
                    }

                await session.commit()

            await state.clear()

            await show_messages_for_application(
                state=state,
                bot=bot,
                telegram_chat_id=u['telegram_chat_id'],
                avito_chat_id=a['avito_chat_id'],
                avito_user_id=a['user_id'],
                author_id=a['author_id'],
                username=a['username']
            )

            await state.set_state(States.message)
        except Exception as e:
            print(e)

    dp.include_router(router)
