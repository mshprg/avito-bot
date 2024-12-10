from aiogram import Router, types, Bot
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import config
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import add_state_id, send_state_message
from models.user import User
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    # Обработчик команды /admins для отображения списка администраторов
    @router.message(Command('admins'), StateFilter(None, States.message))
    async def show_admins(message: types.Message, state: FSMContext):
        try:
            # Сохраняем ID сообщения в состоянии FSM
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="admin_ids"
            )
            # Проверяем, является ли пользователь коренным админом
            if message.from_user.id in config.ROOT_USER_IDS:
                async with AsyncSessionLocal() as session:
                    async with session.begin():
                        # Получаем всех администраторов, кроме себя самого
                        result = await session.execute(
                            select(User).filter(and_(
                                User.admin == True,
                                User.telegram_chat_id != message.chat.id
                            ))
                        )
                        users = result.scalars().all()

                        if len(users) == 0:
                            # Если администраторы не найдены, отправляем сообщение
                            await send_state_message(
                                state=state,
                                message=message,
                                text="Пусто",
                                state_name="admin_ids"
                            )
                            return

                        # Отправляем информацию о каждом найденном администраторе
                        for user in users:
                            text = f"<b>{user.name}\n\n{user.phone}\n\n{user.city}</b>"
                            await send_state_message(
                                state=state,
                                message=message,
                                text=text,
                                parse_mode=ParseMode.HTML,
                                state_name="admin_ids"
                            )

                # Предлагаем действия для управления администраторами
                await send_state_message(
                    state=state,
                    message=message,
                    text="Действия",
                    keyboard=kb.create_delete_admin_messages_keyboard(),
                    state_name="admin_ids"
                )
        except Exception as e:
            print(e)

    # Универсальный обработчик для настройки состояния изменения прав администратора
    async def change_admin_command_handler(text: str, state_name: str, state_to_set, message: types.Message,
                                           state: FSMContext):
        # Сохраняем ID сообщения в состоянии FSM
        await add_state_id(
            state=state,
            message_id=message.message_id,
            state_name=state_name
        )
        # Проверяем, является ли пользователь коренным админом
        if message.from_user.id in config.ROOT_USER_IDS:
            # Отправляем сообщение с указанием дальнейших действий
            await send_state_message(
                state=state,
                message=message,
                text=text,
                state_name=state_name
            )
            # Устанавливаем новое состояние
            await state.set_state(state_to_set)
            return True

        return False

    # Обработчик команды /mkadmin для предоставления пользователю прав администратора
    @router.message(Command('mkadmin'), StateFilter(None, States.message))
    async def make_admin(message: types.Message, state: FSMContext):
        try:
            # Вызываем универсальный обработчик для настройки состояния
            b = await change_admin_command_handler(
                state=state,
                message=message,
                state_name="make_admin_ids",
                state_to_set=States.admin_change,
                text="Введите номер телефона пользователя"
            )
            if b:
                # Сохраняем в состояние тип операции (добавление прав администратора)
                await state.update_data(admin_change="add")
        except Exception as e:
            print(e)

    # Обработчик команды /rmadmin для лишения пользователя прав администратора
    @router.message(Command('rmadmin'), StateFilter(None, States.message))
    async def delete_admin(message: types.Message, state: FSMContext):
        try:
            # Вызываем универсальный обработчик для настройки состояния
            b = await change_admin_command_handler(
                state=state,
                message=message,
                state_name="make_admin_ids",
                state_to_set=States.admin_change,
                text="Введите номер телефона пользователя"
            )
            if b:
                # Сохраняем в состояние тип операции (удаление прав администратора)
                await state.update_data(admin_change="remove")
        except Exception as e:
            print(e)

    # Обработчик для проверки номера телефона при изменении прав администратора
    @router.message(States.admin_change, UserFilter(check_admin=True))
    async def check_admin_phone(message: types.Message, state: FSMContext):
        try:
            # Сохраняем ID сообщения в состоянии FSM
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="make_admin_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Получаем номер телефона из сообщения
                    phone = message.text
                    # Ищем пользователя по номеру телефона
                    result = await session.execute(
                        select(User).filter(User.phone == phone)
                    )
                    user = result.scalars().first()

                    # Получаем тип операции (добавление или удаление)
                    data = await state.get_data()
                    change = data.get("admin_change", None)

                    if change is None:
                        return

                    if user is None:
                        # Если пользователь не найден, отправляем сообщение об ошибке
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Такого пользователя не найдено",
                            state_name="make_admin_ids"
                        )
                        return

                    if user.banned:
                        # Если пользователь заблокирован, уведомляем об этом
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Ошибка: пользователь заблокирован",
                            keyboard=kb.create_delete_admin_messages_keyboard(),
                            state_name="make_admin_ids"
                        )
                        return

                    # Обновляем права пользователя в зависимости от типа операции
                    text = "Ошибка"
                    if change == "add":
                        user.admin = True
                        text = "Пользователю предоставлены права администратора"
                    elif change == "remove":
                        user.admin = False
                        text = "Пользователь лишён прав администратора"

                    # Сбрасываем тип операции в состоянии
                    await state.update_data(admin_change="")

                # Сохраняем изменения в базе данных
                await session.commit()

            # Отправляем сообщение об успешном выполнении операции
            await send_state_message(
                state=state,
                message=message,
                text=text,
                keyboard=kb.create_delete_admin_messages_keyboard(),
                state_name="make_admin_ids"
            )
        except Exception as e:
            # Запрашиваем номер телефона заново
            print(e)
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, введите телефон заново",
                state_name="make_admin_ids"
            )
            await state.set_state(States.admin_change)

    dp.include_router(router)
