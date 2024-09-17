import io
import time
from time import sleep

from aiogram import Router, Bot, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InputMediaPhoto
from sqlalchemy import and_, select

import callbacks
import kb
import s3_cloud
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import delete_message_ids, delete_state_messages, send_state_message, add_state_id
from models.application import Application
from models.image import Image
from models.subscription import Subscription
from models.user import User
from robokassa.payment import create_payment_link
from states import States

media_groups = {}


def load_handlers(dp, bot: Bot):
    router = Router()
    from applications import show_applications

    @router.callback_query(F.data == callbacks.FINISH_APPLICATION_CALLBACK, UserFilter())
    async def finish_application(callback_query: types.CallbackQuery):
        try:
            text = "<b>Вы уверены что хотите завершить работу по заявке?</b>"

            await bot.edit_message_text(
                text=text,
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                reply_markup=kb.create_finish_application_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.BACK_TO_APPLICATION_CALLBACK, UserFilter())
    async def back_to_application(callback_query: types.CallbackQuery):
        try:
            text = (
                "*Дествия с зявкой:*\n_Завершить работу_ \- работа по зявке полностью выполнена, оплата получена\n"
                "_Отказаться от заявки_ \- отказ от работы с заявкой, вы больше не сможете взять эту заявку")

            await bot.edit_message_text(
                text=text,
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                reply_markup=kb.create_application_actions_keyboard(),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.EXACTLY_FINISH_CALLBACK, UserFilter())
    async def close_application_callback(callback_query: types.CallbackQuery, state: FSMContext):
        from applications import get_application_by_user
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(User.telegram_user_id == callback_query.from_user.id)
                    )
                    user = result.scalars().first()

                    result = await session.execute(
                        select(Subscription).filter(Subscription.telegram_user_id == callback_query.from_user.id)
                    )
                    subscription = result.scalars().first()

                    if subscription is None:
                        ...

                    application, work = await get_application_by_user(session, callback_query.message.chat.id)

                    application.in_working = False
                    user.in_working = False

                    await session.delete(work)

                await session.commit()

            try:
                await bot.delete_message(
                    chat_id=user.telegram_chat_id,
                    message_id=callback_query.message.id
                )
            except Exception as e:
                pass

            await send_state_message(
                state=state,
                bot=bot,
                text="Благодарим за работу, сейчас появиться список новых заявок",
                chat_id=callback_query.message.chat.id
            )

            sleep(3)

            await delete_state_messages(
                state=state,
                bot=bot,
                chat_id=callback_query.message.chat.id
            )

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await delete_message_ids(
                        session=session,
                        bot=bot,
                        telegram_chat_id=callback_query.message.chat.id
                    )

                await session.commit()

            await state.clear()

            await show_applications(
                chat_id=callback_query.message.chat.id,
                user_id=callback_query.from_user.id,
                bot=bot
            )

        except Exception as e:
            print(e)

    dp.include_router(router)
