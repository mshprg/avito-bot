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

    @router.message(Command('admins'), StateFilter(None, States.message))
    async def show_admins(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="admin_ids"
            )
            if message.from_user.id in config.ROOT_USER_IDS:
                async with AsyncSessionLocal() as session:
                    async with session.begin():
                        result = await session.execute(
                            select(User).filter(and_(
                                User.admin == True,
                                User.telegram_chat_id != message.chat.id
                            ))
                        )
                        users = result.scalars().all()

                        if len(users) == 0:
                            await send_state_message(
                                state=state,
                                message=message,
                                text="Пусто",
                                state_name="admin_ids"
                            )
                            return

                        for user in users:
                            text = f"<b>{user.name}\n\n{user.phone}\n\n{user.city}</b>"
                            await send_state_message(
                                state=state,
                                message=message,
                                text=text,
                                parse_mode=ParseMode.HTML,
                                state_name="admin_ids"
                            )

                await send_state_message(
                    state=state,
                    message=message,
                    text="Действия",
                    keyboard=kb.create_delete_admin_messages_keyboard(),
                    state_name="admin_ids"
                )
        except Exception as e:
            print(e)

    async def change_admin_command_handler(text: str, state_name: str, state_to_set, message: types.Message, state: FSMContext):
        await add_state_id(
            state=state,
            message_id=message.message_id,
            state_name=state_name
        )
        if message.from_user.id in config.ROOT_USER_IDS:
            await send_state_message(
                state=state,
                message=message,
                text=text,
                state_name=state_name
            )
            await state.set_state(state_to_set)
            return True

        return False

    @router.message(Command('mkadmin'), StateFilter(None, States.message))
    async def make_admin(message: types.Message, state: FSMContext):
        try:
            b = await change_admin_command_handler(
                state=state,
                message=message,
                state_name="make_admin_ids",
                state_to_set=States.admin_change,
                text="Введите номер телефона пользователя"
            )
            if b:
                await state.update_data(admin_change="add")
        except Exception as e:
            print(e)

    @router.message(Command('rmadmin'), StateFilter(None, States.message))
    async def delete_admin(message: types.Message, state: FSMContext):
        try:
            b = await change_admin_command_handler(
                state=state,
                message=message,
                state_name="make_admin_ids",
                state_to_set=States.admin_change,
                text="Введите номер телефона пользователя"
            )
            if b:
                await state.update_data(admin_change="remove")
        except Exception as e:
            print(e)

    @router.message(States.admin_change, UserFilter(check_admin=True))
    async def check_admin_phone(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="make_admin_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    phone = message.text
                    result = await session.execute(
                        select(User).filter(User.phone == phone)
                    )
                    user = result.scalars().first()

                    data = await state.get_data()
                    change = data.get("admin_change", None)

                    if change is None:
                        return

                    if user is None:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Такого пользователя не найдено",
                            state_name="make_admin_ids"
                        )
                        return

                    if user.banned:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Ошибка: пользователь заблокирован",
                            keyboard=kb.create_delete_admin_messages_keyboard(),
                            state_name="make_admin_ids"
                        )
                        return

                    text = "Ошибка"
                    if change == "add":
                        user.admin = True
                        text = "Пользователю предоставлены права администратора"
                    elif change == "remove":
                        user.admin = False
                        text = "Пользователь лишён прав администратора"

                    await state.update_data(admin_change="")

                await session.commit()

            await send_state_message(
                state=state,
                message=message,
                text=text,
                keyboard=kb.create_delete_admin_messages_keyboard(),
                state_name="make_admin_ids"
            )
        except Exception as e:
            print(e)
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, введите телефон заново",
                state_name="make_admin_ids"
            )
            await state.set_state(States.admin_change)

    dp.include_router(router)
