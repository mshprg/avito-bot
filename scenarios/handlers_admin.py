import time
from operator import and_

from aiogram import Router, Bot, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

import callbacks
from db import AsyncSessionLocal
from message_processing import delete_state_messages, add_state_id, reset_state
from models.addiction import Addiction
from models.subscription import Subscription
from models.user import User
from states import States


def load_handlers_admin(dp, bot: Bot):
    router = Router()

    @router.message(Command('cancel'), StateFilter("*"))
    async def cancel(message: types.Message, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await reset_state(state)

                    result = await session.execute(
                        select(User).filter(User.telegram_user_id == message.from_user.id)
                    )
                    user = result.scalars().first()

                    if user is None:
                        return

                    if user.in_working:
                        await state.set_state(States.message)

            await bot.delete_message(
                chat_id=message.chat.id,
                message_id=message.message_id
            )
            await bot.send_message(
                chat_id=message.chat.id,
                text="Действие отменено"
            )
        except Exception as e:
            print(e)

    @router.message(Command('reload'), StateFilter(None, States.message))
    async def reload(message: types.Message, state: FSMContext):
        from message_processing import delete_message_ids
        from applications import show_applications, show_messages_for_application, get_application_by_user
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await delete_state_messages(
                        state=state,
                        bot=bot,
                        chat_id=message.chat.id
                    )

                    await delete_message_ids(
                        session=session,
                        bot=bot,
                        telegram_chat_id=message.chat.id
                    )

                    result = await session.execute(
                        select(User).filter(User.telegram_chat_id == message.chat.id)
                    )
                    user = result.scalars().first()

                    if user is None:
                        return

                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_chat_id == message.chat.id)
                    )
                    addictions = result.scalars().all()

                    for ad in addictions:
                        try:
                            await bot.delete_message(
                                chat_id=message.chat.id,
                                message_id=ad.telegram_message_id,
                            )
                        except:
                            ...
                        await session.delete(ad)

                    result = await session.execute(
                        select(Subscription).filter(and_(
                            Subscription.telegram_user_id == message.chat.id,
                            Subscription.end_time > int(time.time() * 1000)
                        ))
                    )
                    subscription = result.scalars().first()

                    if subscription:
                        is_subscription = True
                    else:
                        is_subscription = False

                    if user.in_working:
                        application, _ = await get_application_by_user(session, message.from_user.id)

                        in_working = True
                        u = {'telegram_chat_id': user.telegram_chat_id}
                        a = {
                            'avito_chat_id': application.avito_chat_id,
                            'user_id': application.user_id,
                            'author_id': application.author_id,
                            'username': application.username
                        }
                    else:
                        in_working = False

            await state.clear()

            if in_working:
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
            elif is_subscription:
                await show_applications(
                    chat_id=message.chat.id,
                    user_id=message.from_user.id,
                    bot=bot
                )
            else:
                await bot.send_message(
                    chat_id=message.chat.id,
                    text="Время действия вашей подписки истекло"
                )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.DELETE_MESSAGES_CALLBACK)
    async def delete_messages(callback_query: types.CallbackQuery, state: FSMContext):
        state_ids = ["admin_ids", "shop_ids", "cities_ids", "make_admin_ids", "report_ids",
                     "location_ids", "feedback_ids", "feedback_admin_ids", "payments_admin_ids", "ban_ids",
                     "user_ids", "video_ids", "sending_ids", "subscribe_ids"]
        try:
            for state_name in state_ids:
                data = await state.get_data()
                ids = data.get(state_name, [])
                if callback_query.message.message_id in ids:
                    if state_name == "feedback_admin_ids":
                        await state.update_data(visible_feedbacks={})
                    await delete_state_messages(
                        state=state,
                        bot=bot,
                        chat_id=callback_query.message.chat.id,
                        state_name=state_name,
                    )
                    await reset_state(state)

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(User.telegram_chat_id == callback_query.message.chat.id)
                    )
                    user = result.scalars().first()

                    if user is None:
                        return

                    if user.in_working:
                        await state.set_state(States.message)
        except Exception as e:
            print(e)

    dp.include_router(router)
