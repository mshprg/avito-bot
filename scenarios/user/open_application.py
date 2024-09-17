import time

from aiogram import Router, Bot, types, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import callbacks
from db import AsyncSessionLocal
from filters import UserFilter
from models.addiction import Addiction
from models.application import Application
from models.subscription import Subscription
from models.user import User
from models.work import Work
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()
    from applications import show_messages_for_application

    @router.callback_query(F.data == callbacks.TAKE_APPLICATION_CALLBACK, UserFilter())
    async def select_application(callback_query: types.CallbackQuery, state: FSMContext):
        from applications import delete_messages_for_application, delete_applications_for_user
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
                        select(User).filter(
                            User.telegram_user_id == callback_query.from_user.id)
                    )
                    user = result.scalars().first()

                    if user is None:
                        return

                    result = await session.execute(
                        select(Subscription).filter(and_(
                            Subscription.telegram_user_id == callback_query.from_user.id,
                            Subscription.end_time > int(time.time() * 1000)
                        ))
                    )
                    subscription = result.scalars().first()

                    if not subscription:
                        await bot.send_message(
                            text="Ваша подписка прекратила действие, оплатите её чтобы продолжить работу над заявками,"
                                 " для этого нажмите кнопку \"Информация о подписке\" на клавиатуре",
                            chat_id=callback_query.message.chat.id,
                            parse_mode=ParseMode.HTML,
                        )
                        await delete_applications_for_user(session, bot, user.telegram_chat_id)
                        return

                    user.in_working = True

                    application.in_working = True
                    application.working_user_id = callback_query.from_user.id

                    work = Work(
                        application_id=application.id,
                        telegram_user_id=user.telegram_user_id
                    )

                    session.add(work)

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
