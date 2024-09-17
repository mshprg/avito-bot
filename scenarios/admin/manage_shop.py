from aiogram import types, F, Router, Bot
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id, reset_state
from models.shop import Shop
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(Command('shop'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def check_commission(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="shop_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Shop)
                    )
                    shop = result.scalars().first()

                    if shop is not None:
                        price_30days = shop.subscribe_30days

                        text = f"<b>Текущие цены:</b>\nПодписка на 30 дней - {price_30days} руб."
                        await send_state_message(
                            state=state,
                            message=message,
                            text=text,
                            parse_mode=ParseMode.HTML,
                            keyboard=kb.create_manage_shop_keyboard(),
                            state_name="shop_ids"
                        )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.CHANGE_30_CALLBACK, UserFilter(check_admin=True))
    async def change_fixed_callback(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Введите новую цену",
                state_name="shop_ids"
            )
            await state.set_state(States.shop_price)
        except Exception as e:
            print(e)

    @router.message(States.shop_price, UserFilter(check_admin=True))
    async def change_fixed_commission(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="shop_ids"
            )
            cm = float(message.text)
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Shop)
                    )
                    shop = result.scalars().first()

                    if shop is None or cm < 0:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Ошибка, повторите ввод",
                            state_name="shop_ids"
                        )
                        await state.set_state(States.shop_price)
                        return

                    shop.subscribe_30days = cm

                await session.commit()

            await send_state_message(
                state=state,
                message=message,
                text="Цена успешно изменена",
                keyboard=kb.create_delete_admin_messages_keyboard(),
                state_name="shop_ids"
            )

            await reset_state(
                state=state
            )
        except Exception as e:
            print(e)
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите ввод",
                state_name="shop_ids"
            )
            await state.set_state(States.shop_price)

    dp.include_router(router)
