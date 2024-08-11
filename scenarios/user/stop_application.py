from aiogram import Router, Bot, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, delete_state_messages, delete_message_ids, add_state_id
from models.application import Application
from models.mask import Mask
from models.user import User
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()
    from applications import show_applications, show_application

    @router.callback_query(F.data == callbacks.STOP_APPLICATION_CALLBACK, UserFilter())
    async def stop_application(callback_query: types.CallbackQuery):
        try:
            text = "<b>Вы уверены что хотите отказаться от заявки?</b>"

            await bot.edit_message_text(
                text=text,
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                reply_markup=kb.create_stop_application_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.EXACTLY_STOP_CALLBACK, UserFilter())
    async def exactly_stop_application(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == callback_query.message.chat.id)
                    )
                    user = result.scalars().first()

                    result = await session.execute(
                        select(User).filter(User.in_working == False)
                    )
                    other_users = result.scalars().all()

                    result = await session.execute(
                        select(Application).filter(and_(
                            Application.working_user_id == callback_query.message.chat.id,
                            Application.in_working == True,
                        ))
                    )
                    application = result.scalars().first()

                    if application.pay_type == "fixed":
                        await send_state_message(
                            state=state,
                            message=callback_query.message,
                            text="Отправьте номер карты на которую вам нужно вернуть комиссию",
                        )
                        await state.set_state(States.user_card_number)
                        return

                    mask = Mask(
                        application_id=application.id,
                        user_id=user.id,
                        telegram_user_id=callback_query.from_user.id,
                    )
                    session.add(mask)

                    application.in_working = False
                    application.working_user_id = -1
                    application.pay_type = "None"
                    application.com_value = 0
                    user.in_working = False

                    for u in other_users:
                        if u.telegram_chat_id != callback_query.message.chat.id:
                            await show_application(
                                session=session,
                                application=application,
                                bot=bot,
                                chat_id=u.telegram_chat_id,
                                user_city=u.city,
                                is_admin=u.admin
                            )

                    await delete_message_ids(
                        session=session,
                        bot=bot,
                        telegram_chat_id=callback_query.message.chat.id
                    )

                await session.commit()

            await delete_state_messages(
                state=state,
                bot=bot,
                chat_id=callback_query.message.chat.id
            )

            await state.clear()

            await show_applications(
                chat_id=callback_query.message.chat.id,
                user_id=callback_query.from_user.id,
                bot=bot
            )
        except Exception as e:
            print(e)

    @router.message(States.user_card_number, UserFilter())
    async def read_user_card_number(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id
            )
            number = int(message.text)
            if len(message.text) != 16:
                raise Exception("Invalid length")
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == message.from_user.id)
                    )
                    user = result.scalars().first()

                    result = await session.execute(
                        select(User).filter(User.in_working == False)
                    )
                    other_users = result.scalars().all()

                    result = await session.execute(
                        select(Application).filter(and_(
                            Application.working_user_id == message.chat.id,
                            Application.in_working == True,
                        ))
                    )
                    application = result.scalars().first()

                    result = await session.execute(
                        select(User).filter(User.admin == True)
                    )
                    admin_users = result.scalars().all()

                    for u in admin_users:
                        try:
                            text = (f"Пользователь отменил заявку, требуется вернуть комиссию в размере "
                                    f"<b>{int(application.com_value) / 2} руб.</b> на карту <b>{number}</b>")
                            await bot.send_message(
                                chat_id=u.telegram_chat_id,
                                text=text,
                                parse_mode=ParseMode.HTML,
                            )
                        except:
                            ...

                    mask = Mask(
                        application_id=application.id,
                        user_id=user.id,
                        telegram_user_id=message.from_user.id,
                    )
                    session.add(mask)

                    application.in_working = False
                    application.working_user_id = -1
                    application.pay_type = "None"
                    application.income += int(application.com_value) / 2
                    application.com_value = 0
                    user.in_working = False

                    for u in other_users:
                        if u.telegram_chat_id != message.chat.id:
                            await show_application(
                                session=session,
                                application=application,
                                bot=bot,
                                chat_id=u.telegram_chat_id,
                                user_city=u.city,
                                is_admin=u.admin
                            )

                    await delete_message_ids(
                        session=session,
                        bot=bot,
                        telegram_chat_id=message.chat.id
                    )

                await session.commit()

            await delete_state_messages(
                state=state,
                bot=bot,
                chat_id=message.chat.id
            )

            await state.clear()

            await show_applications(
                chat_id=message.chat.id,
                user_id=message.chat.id,
                bot=bot
            )
        except Exception as e:
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите ввод",
            )
            await state.set_state(States.user_card_number)
            print(e)

    dp.include_router(router)
