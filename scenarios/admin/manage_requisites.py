from aiogram import Router, Bot, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id
from models.requisites import Requisites
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(Command('requisites'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def check_requisites(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="requisites_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Requisites)
                    )
                    requisites = result.scalars().first()

                    if requisites is not None:
                        card = requisites.card_number

                        text = f"Текущий номер карты: *{card}*"
                        await send_state_message(
                            state=state,
                            message=message,
                            text=text,
                            parse_mode=ParseMode.MARKDOWN_V2,
                            keyboard=kb.create_manage_requisites_keyboard(),
                            state_name="requisites_ids",
                        )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.CHANGE_REQUISITES_CALLBACK, UserFilter(check_admin=True))
    async def change_requisites_callback(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            text = "Введите новый номер карты, пример:\n*0000000000000000*"
            await send_state_message(
                state=state,
                message=callback_query.message,
                text=text,
                state_name="requisites_ids",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            await state.set_state(States.requisites)
        except Exception as e:
            print(e)

    @router.message(States.requisites, UserFilter(check_admin=True))
    async def read_requisites_callback(message: types.Message, state: FSMContext):
        try:
            card_number = int(message.text)
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="requisites_ids"
            )
            if len(message.text) != 16:
                await send_state_message(
                    state=state,
                    message=message,
                    text="Ошибка: неверный формат номера",
                    state_name="requisites_ids"
                )
                await state.set_state(States.requisites)
                return
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Requisites)
                    )
                    requisites = result.scalars().first()

                    string = str(card_number)

                    formatted_string = ' '.join([string[i:i + 4] for i in range(0, len(string), 4)])

                    requisites.card_number = formatted_string

                await session.commit()

            await send_state_message(
                state=state,
                message=message,
                text="Номер карты успешно изменён",
                keyboard=kb.create_delete_admin_messages_keyboard(),
                state_name="requisites_ids"
            )
        except Exception as e:
            print(e)
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите ввод",
                state_name="requisites_ids"
            )
            await state.set_state(States.requisites)

    dp.include_router(router)
