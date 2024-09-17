import time
from time import sleep

from aiogram import Router, Bot, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, delete_state_messages, delete_message_ids, add_state_id
from models.mask import Mask
from models.payment import Payment
from models.subscription import Subscription
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
        from applications import get_application_by_user
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == callback_query.message.chat.id)
                    )
                    user = result.scalars().first()

                    result = await session.execute(
                        select(Subscription).filter(Subscription.end_time > int(time.time() * 1000))
                    )
                    subscriptions = result.scalars().all()

                    user_ids = [s.telegram_user_id for s in subscriptions]

                    result = await session.execute(
                        select(User).filter(and_(
                            User.in_working == False,
                            User.banned == False,
                            User.telegram_user_id.in_(user_ids)
                        ))
                    )
                    other_users = result.scalars().all()

                    application, work = await get_application_by_user(session, user.telegram_user_id)

                    mask = Mask(
                        application_id=application.id,
                        user_id=user.id,
                        telegram_user_id=callback_query.from_user.id,
                    )
                    session.add(mask)

                    application.in_working = False
                    application.working_user_id = -1
                    user.in_working = False

                    await session.delete(work)

                    for u in other_users:
                        if u.telegram_chat_id != callback_query.message.chat.id:
                            await show_application(
                                session=session,
                                application=application,
                                bot=bot,
                                chat_id=u.telegram_chat_id,
                                user_city=u.city,
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

    dp.include_router(router)
