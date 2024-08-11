from aiogram import types, F, Router, Bot
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id
from models.comission import Commission
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(Command('commission'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def check_commission(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="commission_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Commission)
                    )
                    commission = result.scalars().first()

                    if commission is not None:
                        percent = commission.percent
                        fixed = commission.fixed

                        text = f"*Текущие комиссии:*\n_Фикс\. комиссия_ \- {fixed} руб\.\n_Комиссия в процентах_ \- {percent}%"
                        await send_state_message(
                            state=state,
                            message=message,
                            text=text,
                            parse_mode=ParseMode.MARKDOWN_V2,
                            keyboard=kb.create_manage_commission_keyboard(),
                            state_name="commission_ids"
                        )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.CHANGE_FIXED_CALLBACK, UserFilter(check_admin=True))
    async def change_fixed_callback(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Введите новую фиксированную комиссию (в рублях), вводите только число >= 0",
                state_name="commission_ids"
            )
            await state.set_state(States.fixed_commission)
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.CHANGE_PERCENT_CALLBACK, UserFilter(check_admin=True))
    async def change_percent_callback(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Введите новую комиссию в процентах от стоимости заказа, вводите только число >= 0\nНапример: 4 "
                     "- комиссия 4% от стоимости заказа",
                state_name="commission_ids"
            )
            await state.set_state(States.percent_commission)
        except Exception as e:
            print(e)

    @router.message(States.fixed_commission, UserFilter(check_admin=True))
    async def change_fixed_commission(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="commission_ids"
            )
            cm = int(message.text)
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Commission)
                    )
                    commission = result.scalars().first()

                    if commission is None or cm < 0:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Ошибка, повторите ввод",
                            state_name="commission_ids"
                        )
                        await state.set_state(States.fixed_commission)
                        return

                    commission.fixed = cm

                await session.commit()

            await send_state_message(
                state=state,
                message=message,
                text="Комиссия успешно изменена",
                keyboard=kb.create_delete_admin_messages_keyboard(),
                state_name="commission_ids"
            )
        except Exception as e:
            print(e)
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите ввод",
                state_name="commission_ids"
            )
            await state.set_state(States.fixed_commission)

    @router.message(States.percent_commission, UserFilter(check_admin=True))
    async def change_percent_commission(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="commission_ids"
            )
            cm = int(message.text)
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Commission)
                    )
                    commission = result.scalars().first()

                    if commission is None or cm < 0:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Ошибка, повторите ввод",
                            state_name="commission_ids"
                        )
                        await state.set_state(States.percent_commission)
                        return

                    commission.percent = cm

                await session.commit()

            await send_state_message(
                state=state,
                message=message,
                text="Комиссия успешно изменена",
                keyboard=kb.create_delete_admin_messages_keyboard(),
                state_name="commission_ids"
            )
        except Exception as e:
            print(e)
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите ввод",
                state_name="commission_ids"
            )
            await state.set_state(States.percent_commission)

    dp.include_router(router)
