from aiogram import Router, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import config
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id
from models.application import Application
from models.user import User
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    # Функция для установки ожидания номера для блокировки/разблокировки пользователя
    async def ban_command_handler(message: types.Message, state: FSMContext, setting_state):
        # Сохраняем ID сообщения в состоянии FSM
        await add_state_id(
            state=state,
            message_id=message.message_id,
            state_name="ban_ids"
        )
        # Отправляем сообщение, запрашивающее ввод номера телефона
        await send_state_message(
            state=state,
            message=message,
            text="Введите номер телефона пользователя",
            state_name="ban_ids"
        )
        # Устанавливаем сосотояние ожидания номера телефона пользователя
        await state.set_state(setting_state)

    # Обработчик команды /ban для начала процесса блокировки пользователя
    @router.message(Command('ban'), UserFilter(check_admin=True))
    async def ban_user(message: types.Message, state: FSMContext):
        try:
            # Вызываем общий обработчик для настройки состояния блокировки
            await ban_command_handler(message, state, States.ban)
        except Exception as e:
            print(e)

    # Обработчик команды /unban для начала процесса разблокировки пользователя
    @router.message(Command('unban'), UserFilter(check_admin=True))
    async def unban_user(message: types.Message, state: FSMContext):
        try:
            # Вызываем общий обработчик для настройки состояния разблокировки
            await ban_command_handler(message, state, States.unban)
        except Exception as e:
            print(e)

    # Обработчик для чтения номера телефона при блокировке пользователя
    @router.message(States.ban, UserFilter(check_admin=True))
    async def read_ban_number(message: types.Message, state: FSMContext):
        from applications import show_application
        try:
            # Сохраняем ID сообщения в состоянии FSM
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="ban_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Получаем номер телефона из сообщения
                    phone = message.text
                    # Ищем пользователя с указанным номером телефона
                    result = await session.execute(
                        select(User).filter(User.phone == phone)
                    )
                    user = result.scalars().first()

                    if user is None:
                        # Если пользователь не найден, отправляем сообщение об ошибке
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Пользователя с таким номером телефона не существует",
                            state_name="ban_ids"
                        )
                        await state.set_state(States.ban)
                        return

                    # Проверка прав доступа для блокировки пользователя
                    if message.from_user.id in config.ROOT_USER_IDS:  # Если данный пользователь коренной админ
                        if user.telegram_user_id not in config.ROOT_USER_IDS:  # Если блокируемый пользвоатель не
                            # коренной админ
                            if user.admin:  # Если блокируемый пользвоатель обычный админ
                                user.admin = False
                            user.banned = True
                        else:
                            # Если недостаточно прав, отправляем сообщение
                            await send_state_message(
                                state=state,
                                message=message,
                                text="У вас недостаточно прав для блокировки этого пользователя",
                                keyboard=kb.create_delete_admin_messages_keyboard(),
                                state_name="ban_ids",
                            )
                    else:
                        if user.telegram_user_id not in config.ROOT_USER_IDS and not user.admin:
                            user.banned = True
                        else:
                            await send_state_message(
                                state=state,
                                message=message,
                                text="У вас недостаточно прав для блокировки этого пользователя",
                                keyboard=kb.create_delete_admin_messages_keyboard(),
                                state_name="ban_ids",
                            )

                    await session.flush()

                    # Если пользователь был в работе, обновляем состояние заявок
                    if user.banned and user.in_working:
                        result = await session.execute(
                            select(Application).filter(and_(
                                Application.working_user_id == user.telegram_user_id,
                                Application.in_working == True,
                            ))
                        )
                        application = result.scalars().first()

                        if application:
                            # Освобождаем заявку и уведомляем других пользователей
                            application.in_working = False
                            application.working_user_id = -1
                            application.com_value = 0
                            user.in_working = False

                            result = await session.execute(
                                select(User).filter(and_(
                                    User.in_working == False,
                                    User.banned == False,
                                ))
                            )
                            users = result.scalars().all()

                            # Показываем заявку другим пользователям
                            for u in users:
                                await show_application(
                                    session=session,
                                    application=application,
                                    user_city=u.city,
                                    bot=bot,
                                    chat_id=u.telegram_chat_id,
                                    is_root_admin=user.admin,
                                )

                    if user.banned:
                        # Сообщаем об успешной блокировке
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Пользователь заблокирован",
                            keyboard=kb.create_delete_admin_messages_keyboard(),
                            state_name="ban_ids",
                        )

                await session.commit()
        except Exception as e:
            # Отправляем сообщение об ошибке
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите попытку",
                state_name="ban_ids"
            )
            await state.set_state(States.ban)
            print(e)

    # Обработчик для чтения номера телефона при разблокировке пользователя
    @router.message(States.unban, UserFilter(check_admin=True))
    async def read_unban_number(message: types.Message, state: FSMContext):
        try:
            # Сохраняем ID сообщения в состоянии FSM
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="ban_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Получаем номер телефона из сообщения
                    phone = message.text
                    # Ищем пользователя с указанным номером телефона
                    result = await session.execute(
                        select(User).filter(User.phone == phone)
                    )
                    user = result.scalars().first()

                    if user is None:
                        # Если пользователь не найден, отправляем сообщение об ошибке
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Пользователя с таким номером телефона не существует",
                            state_name="ban_ids"
                        )
                        await state.set_state(States.unban)
                        return

                    # Снимаем блокировку с пользователя
                    user.banned = False

                    # Сообщаем об успешной разблокировке
                    await send_state_message(
                        state=state,
                        message=message,
                        text="Пользователь разблокирован",
                        keyboard=kb.create_delete_admin_messages_keyboard(),
                        state_name="ban_ids",
                    )

                await session.commit()
        except Exception as e:
            # Отправляем сообщение об ошибке
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите попытку",
                state_name="ban_ids"
            )
            await state.set_state(States.ban)
            print(e)

    dp.include_router(router)
