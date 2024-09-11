from time import sleep

from aiogram import Router, Bot, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id, reset_state
from models.city import City
from models.user import User
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(F.text, Command('sending'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def load_sending(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                state_name="sending_ids",
                message_id=message.message_id
            )

            await send_state_message(
                message=message,
                text="Введите текст рассылки",
                state=state,
                state_name="sending_ids"
            )
            await state.set_state(States.sending_text)
        except Exception as e:
            pass

    @router.message(States.sending_text, UserFilter(check_admin=True))
    async def read_sending_text(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                state_name="sending_ids",
                message_id=message.message_id
            )

            text = message.text

            if text is None:
                raise Exception("Invalid text")

            text = "<b>Сообщение от администратора:</b>\n" + text

            await state.update_data(sending_text=text)

            await send_state_message(
                state=state,
                message=message,
                text="Выберите вариант отправки",
                keyboard=kb.create_select_sending_keyboard(),
                state_name="sending_ids"
            )
        except Exception as e:
            await send_state_message(
                message=message,
                text="Ошибка, повторите ввод",
                state=state,
                state_name="sending_ids"
            )
            await state.set_state(States.sending_text)

    @router.callback_query(F.data == callbacks.SEND_MESSAGE_ALL_CALLBACK, UserFilter(check_admin=True))
    async def send_message_for_all_users(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(and_(
                            User.telegram_user_id != callback_query.message.chat.id,
                            User.banned == False,
                        ))
                    )
                    users = result.scalars().all()

                    chat_ids = [u.telegram_chat_id for u in users]

            data = await state.get_data()
            sending_text = data.get("sending_text", "")

            if len(sending_text) == 0:
                raise Exception("Invalid text")

            for chat_id in chat_ids:
                sleep(0.2)
                await bot.send_message(
                    chat_id=chat_id,
                    text=sending_text,
                    parse_mode=ParseMode.HTML
                )

            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Сообщение отправлено",
                keyboard=kb.create_delete_admin_messages_keyboard(),
                state_name="sending_ids"
            )

            await reset_state(state=state)
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.SELECT_SENDING_CITY_CALLBACK, UserFilter(check_admin=True))
    async def select_sending_city(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(City)
                    )
                    cities_db = result.scalars().all()

                    text = "<b>Введите назавания локаций через запятую и пробел, вот списко всех локаций:</b>\n"

                    for i, city in enumerate(cities_db, start=1):
                        text += f"{i}. {city.city}\n"

                    await send_state_message(
                        state=state,
                        message=callback_query.message,
                        parse_mode=ParseMode.HTML,
                        text=text
                    )
                    await state.set_state(States.sending_locations)
        except Exception as e:
            print(e)

    @router.message(States.sending_locations, UserFilter(check_admin=True))
    async def read_sending_locations(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                state_name="sending_ids",
                message_id=message.message_id
            )

            text = message.text

            if text is None:
                raise Exception("Invalid text")

            data = await state.get_data()
            sending_text = data.get("sending_text", "")

            if len(sending_text) == 0:
                raise Exception("Invalid text")

            locations = text.split(", ")

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(and_(
                            User.city.in_(locations),
                            User.telegram_user_id != message.from_user.id,
                            User.banned == False
                        ))
                    )
                    users = result.scalars().all()

                    chat_ids = [u.telegram_user_id for u in users]

            for chat_id in chat_ids:
                sleep(0.2)
                await bot.send_message(
                    chat_id=chat_id,
                    text=sending_text,
                    parse_mode=ParseMode.HTML
                )

            await send_state_message(
                state=state,
                message=message,
                text="Сообщение отправлено",
                state_name="sending_ids",
                keyboard=kb.create_delete_admin_messages_keyboard()
            )

            await reset_state(state=state)
        except Exception as e:
            pass

    dp.include_router(router)
