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

    # Обработчик команды "/cancel" для отмены текущего действия и сброса состояния
    @router.message(Command('cancel'), StateFilter("*"))
    async def cancel(message: types.Message, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Сбрасывает состояние FSM, но сохраняет данные
                    await reset_state(state)

                    # Получает пользователя из базы данных по Telegram ID
                    result = await session.execute(
                        select(User).filter(User.telegram_user_id == message.from_user.id)
                    )
                    user = result.scalars().first()

                    # Если пользователь не найден, завершает выполнение
                    if user is None:
                        return

                    # Если пользователь находится в состоянии "в работе", устанавливает новое состояние ожидание
                    # ввода сообщения
                    if user.in_working:
                        await state.set_state(States.message)

            # Удаляет сообщение команды "/cancel"
            await bot.delete_message(
                chat_id=message.chat.id,
                message_id=message.message_id
            )
            # Отправляет сообщение пользователю об отмене действия
            await bot.send_message(
                chat_id=message.chat.id,
                text="Действие отменено"
            )
        except Exception as e:
            print(e)

    # Обработчик команды "/reload" для обновления состояния, очистки сообщений и перезагрузки данных бота
    @router.message(Command('reload'), StateFilter(None, States.message))
    async def reload(message: types.Message, state: FSMContext):
        from message_processing import delete_message_ids
        from applications import show_applications, show_messages_for_application, get_application_by_user
        try:
            # Добавляет ID текущего сообщения в состояние
            await add_state_id(
                state=state,
                message_id=message.message_id
            )

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Удаляет сообщения, связанные с текущим состоянием FSM
                    await delete_state_messages(
                        state=state,
                        bot=bot,
                        chat_id=message.chat.id
                    )

                    # Удаляет записи сообщений чата из базы данных
                    await delete_message_ids(
                        session=session,
                        bot=bot,
                        telegram_chat_id=message.chat.id
                    )

                    # Получает данные о пользователе из базы данных
                    result = await session.execute(
                        select(User).filter(User.telegram_chat_id == message.chat.id)
                    )
                    user = result.scalars().first()

                    # Если пользователь не найден, завершает выполнение
                    if user is None:
                        return

                    # Получает все зависимости между заявками их сообщениями в чате пользователя
                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_chat_id == message.chat.id
                        )
                    )
                    addictions = result.scalars().all()

                    for ad in addictions:
                        try:
                            # Удаляет сообщения зависимости
                            await bot.delete_message(
                                chat_id=message.chat.id,
                                message_id=ad.telegram_message_id,
                            )
                        except:
                            ...  # Игнорирует ошибки при удалении сообщения
                        await session.delete(ad)  # Удаляет запись зависимости из базы данных

                    # Проверяет, есть ли активная подписка пользователя
                    result = await session.execute(
                        select(Subscription).filter(and_(
                            Subscription.telegram_user_id == message.chat.id,
                            Subscription.end_time > int(time.time() * 1000)  # Подписка должна быть активной
                        ))
                    )
                    subscription = result.scalars().first()
                    is_subscription = bool(subscription)

                    # Проверяет, находится ли пользователь в состоянии "в работе"
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

            # Очищает состояние FSM
            await state.clear()

            if in_working:
                # Если пользователь работает с заявкой, отображает сообщения этой заявки
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
                # Если есть активная подписка, отображает доступные заявки
                await show_applications(
                    chat_id=message.chat.id,
                    user_id=message.from_user.id,
                    bot=bot
                )
            else:
                # Если подписка истекла, уведомляет пользователя
                await bot.send_message(
                    chat_id=message.chat.id,
                    text="Время действия вашей подписки истекло"
                )
        except Exception as e:
            print(e)

    # Обработчик callback-запроса для удаления всех сообщений, связанных с определённым состоянием
    @router.callback_query(F.data == callbacks.DELETE_MESSAGES_CALLBACK)
    async def delete_messages(callback_query: types.CallbackQuery, state: FSMContext):
        # Список возможных состояний, для которых сообщения могут быть удалены
        state_ids = [
            "admin_ids", "shop_ids", "cities_ids", "make_admin_ids", "report_ids",
            "location_ids", "feedback_ids", "feedback_admin_ids", "payments_admin_ids", "ban_ids",
            "user_ids", "video_ids", "sending_ids", "subscribe_ids"
        ]
        try:
            # Перебираем каждое состояние в списке
            for state_name in state_ids:
                # Получаем данные состояния FSM
                data = await state.get_data()
                ids = data.get(state_name, [])

                # Проверяем, содержится ли ID текущего сообщения в списке ID этого состояния
                if callback_query.message.message_id in ids:
                    # Если состояние связано с админской обратной связью, очищаем данные видимых отзывов
                    if state_name == "feedback_admin_ids":
                        await state.update_data(visible_feedbacks={})

                    # Удаляем все сообщения, связанные с этим состоянием
                    await delete_state_messages(
                        state=state,
                        bot=bot,
                        chat_id=callback_query.message.chat.id,
                        state_name=state_name,
                    )
                    # Сбрасываем текущее состояние FSM, но сохраняем другие данные
                    await reset_state(state)

            # Работа с базой данных
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Получаем данные пользователя по Telegram ID
                    result = await session.execute(
                        select(User).filter(User.telegram_chat_id == callback_query.message.chat.id)
                    )
                    user = result.scalars().first()

                    # Если пользователь не найден, завершаем обработчик
                    if user is None:
                        return

                    # Если пользователь находится "в работе", устанавливаем соответствующее состояние
                    if user.in_working:
                        await state.set_state(States.message)
        except Exception as e:
            print(e)

    dp.include_router(router)
