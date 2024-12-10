import time

from aiogram import Router, Bot, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import delete_state_messages, delete_message_ids
from models.mask import Mask
from models.subscription import Subscription
from models.user import User


def load_handlers(dp, bot: Bot):
    router = Router()
    from applications import show_applications, show_application

    # Обработка нажатия кнопки "Отказаться от заявки"
    @router.callback_query(F.data == callbacks.STOP_APPLICATION_CALLBACK, UserFilter())
    async def stop_application(callback_query: types.CallbackQuery):
        try:
            # Генерируем текст
            text = "<b>Вы уверены что хотите отказаться от заявки?</b>"

            # Меняем текст и кнопки сообщения
            await bot.edit_message_text(
                text=text,
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                reply_markup=kb.create_stop_application_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            print(e)

    # Пользователь точно хочет отказаться от заявки
    @router.callback_query(F.data == callbacks.EXACTLY_STOP_CALLBACK, UserFilter())
    async def exactly_stop_application(callback_query: types.CallbackQuery, state: FSMContext):
        from applications import get_application_by_user
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Находим юзера в бд
                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == callback_query.message.chat.id)
                    )
                    user = result.scalars().first()

                    # Находим активные подписки всех юзеров
                    result = await session.execute(
                        select(Subscription).filter(Subscription.end_time > int(time.time() * 1000))
                    )
                    subscriptions = result.scalars().all()

                    # Выделяем из них id юзеров
                    user_ids = list(set([s.telegram_user_id for s in subscriptions]))

                    # Находим этих юзеров, при условии что они не работают над заявкой и они не в бане
                    result = await session.execute(
                        select(User).filter(and_(
                            User.in_working == False,
                            User.banned == False,
                            User.telegram_user_id.in_(user_ids)
                        ))
                    )
                    other_users = result.scalars().all()

                    # Получаем данные о заявке и о состоянии работы для данного юзера
                    application, work = await get_application_by_user(session, user.telegram_user_id)

                    # Создаем маску для юзера, чтобы он больше не мог видеть данную заявку
                    mask = Mask(
                        application_id=application.id,
                        user_id=user.id,
                        telegram_user_id=callback_query.from_user.id,
                    )
                    session.add(mask)

                    # Меняем сосотояние юзера и заявки
                    application.in_working = False
                    application.working_user_id = -1
                    user.in_working = False

                    # Удаляем запись о работе юзера для данной заявки
                    await session.delete(work)

                    # Показываем заявки другим подходящим юзерам
                    for u in other_users:
                        if u.telegram_chat_id != callback_query.message.chat.id:
                            await show_application(
                                session=session,
                                application=application,
                                bot=bot,
                                chat_id=u.telegram_chat_id,
                                user_city=u.city,
                                is_root_admin=u.admin,
                            )

                    # Удаляем отправленные в чате сообщения у данного юзера
                    await delete_message_ids(
                        session=session,
                        bot=bot,
                        telegram_chat_id=callback_query.message.chat.id
                    )

                await session.commit()

            # Удалем сообщения из стейта
            await delete_state_messages(
                state=state,
                bot=bot,
                chat_id=callback_query.message.chat.id
            )

            await state.clear()

            # Показываем юзеру другие заявки
            await show_applications(
                chat_id=callback_query.message.chat.id,
                user_id=callback_query.from_user.id,
                bot=bot
            )
        except Exception as e:
            print(e)

    dp.include_router(router)
