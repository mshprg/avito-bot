from aiogram import Bot, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id, reset_state
from models.user import User
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(Command('users'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def show_users(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                state_name="user_ids",
                message_id=message.message_id
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User)
                    )
                    users = result.scalars().all()

                    if len(users) == 0:
                        return

                    await send_state_message(
                        message=message,
                        text=f"Общее количество пользователей: <b>{len(users)}</b>",
                        parse_mode=ParseMode.HTML,
                        state=state,
                        state_name="user_ids"
                    )

                    for user in users:
                        dop = ""
                        if user.telegram_user_id == message.from_user.id:
                            dop = "<b>|- - - Ваш аккаунт - - -|</b>\n"
                        text = dop + (f"<b>Имя: </b>{user.name}\n"
                                      f"<b>Номер телефона: </b>{user.phone}\n"
                                      f"<b>ID пользователя: </b>{user.telegram_user_id}\n"
                                      f"<b>Статус аккаунта: </b>{'администратор' if user.admin else 'пользователь'}\n"
                                      f"<b>Город: </b>{user.city}\n"
                                      f"<b>Блокировка: </b>{'заблокирован' if user.banned else 'разблокирован'}\n"
                                      f"<b>Работа: </b>{'работает над заявкой' if user.in_working else 'не работает'}")
                        await send_state_message(
                            message=message,
                            text=text,
                            parse_mode=ParseMode.HTML,
                            state=state,
                            state_name="user_ids"
                        )

            await send_state_message(
                state=state,
                text="Действия",
                message=message,
                state_name="user_ids",
                keyboard=kb.create_delete_admin_messages_keyboard()
            )
        except Exception as e:
            print(e)
            await send_state_message(
                state=state,
                text="Ошибка, повторите попытку",
                message=message,
                state_name="user_ids",
            )

    @router.message(Command('user'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def show_user(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                state_name="user_ids",
                message_id=message.message_id
            )
            await send_state_message(
                state=state,
                text="Введите номер телефона пользователя",
                message=message,
                state_name="user_ids",
            )
            await state.set_state(States.user_ids)
        except Exception as e:
            await send_state_message(
                state=state,
                text="Ошибка, повторите попытку",
                message=message,
                state_name="user_ids",
            )
            await state.set_state(States.user_ids)
            print(e)

    @router.message(States.user_ids, UserFilter(check_admin=True))
    async def read_user_phone(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                state_name="user_ids",
                message_id=message.message_id
            )

            phone = message.text

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(User.phone == phone)
                    )
                    user = result.scalars().first()

                    if user is None:
                        await send_state_message(
                            state=state,
                            text="Пользователь не найден, повторите попытку",
                            message=message,
                            state_name="user_ids",
                        )
                        await state.set_state(States.user_ids)
                        return

                    text = (f"<b>Имя: </b>{user.name}\n"
                            f"<b>Номер телефона: </b>{user.phone}\n"
                            f"<b>ID пользователя: </b>{user.telegram_user_id}\n"
                            f"<b>Статус аккаунта: </b>{'администратор' if user.admin else 'пользователь'}\n"
                            f"<b>Город: </b>{user.city}\n"
                            f"<b>Блокировка: </b>{'заблокирован' if user.banned else 'разблокирован'}\n"
                            f"<b>Работа: </b>{'работает над заявкой' if user.in_working else 'не работает'}")

                    await send_state_message(
                        message=message,
                        text=text,
                        parse_mode=ParseMode.HTML,
                        state=state,
                        state_name="user_ids",
                        keyboard=kb.create_delete_admin_messages_keyboard()
                    )

                    await reset_state(state)
        except Exception as e:
            print(e)
            await send_state_message(
                state=state,
                text="Ошибка, повторите попытку",
                message=message,
                state_name="user_ids",
            )
            await state.set_state(States.user_ids)

    dp.include_router(router)
