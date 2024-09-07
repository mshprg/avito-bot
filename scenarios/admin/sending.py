from time import sleep

from aiogram import Router, Bot, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message
from models.city import City
from models.user import User
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(F.text, Command('sending'), UserFilter(check_admin=True))
    async def load_sending(message: types.Message, state: FSMContext):
        try:
            await send_state_message(
                message=message,
                text="Введите текст рассылки",
                state=state,
                state_name="sending_ids"
            )
            await state.set_state(States.sending_text)
        except Exception as e:
            pass

    @router.message(States.sending_text)
    async def read_sending_text(message: types.Message, state: FSMContext):
        try:
            text = message.text

            if text is None:
                raise Exception("Invalid text")

            await state.update_data(sending_text=text)

            await send_state_message(
                state=state,
                message=message,
                text="Выберите вариант отправки",
                keyboard=kb.create_select_sending_keyboard()
            )
        except Exception as e:
            await send_state_message(
                message=message,
                text="Ошибка, повторите ввод",
                state=state,
                state_name="sending_ids"
            )
            await state.set_state(States.sending_text)

    @router.message(F.data == callbacks.SEND_MESSAGE_ALL_CALLBACK)
    async def send_message_for_all_users(message: types.Message, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(and_(
                            User.telegram_user_id != message.chat.id,
                            User.banned == False,
                        ))
                    )
                    users = result.scalars().all()

                    ids = [u.telegram_chat_id for u in users]

            data = await state.get_data()
            sending_text = data.get("sending_text", "")

            if len(sending_text) == 0:
                raise Exception("Invalid text")

            for chat_id in ids:
                sleep(0.2)
                await bot.send_message(
                    chat_id=chat_id,
                    text=sending_text
                )
        except Exception as e:
            pass

    @router.message(F.data == callbacks.SELECT_SENDING_CITY_CALLBACK)
    async def select_sending_city(message: types.Message, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(City)
                    )
                    cities_db = result.scalars().all()

                    text = "<b>Введите назавания локаций через запятую и пробел, вот списко всех локаций:</b>\n"

                    for i, city in enumerate(cities_db, start=1):
                        text += f"{i}. {city.name}\n"

                    await send_state_message(
                        state=state,
                        message=message,
                        parse_mode=ParseMode.HTML,
                        text=text
                    )
                    await state.set_state(States.sending_locations)
        except Exception as e:
            pass

    @router.message(States.sending_locations)
    async def read_sending_locations(message: types.Message, state: FSMContext):
        try:
            ...
        except Exception as e:
            pass

    dp.include_router(router)
