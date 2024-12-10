from aiogram import types, F, Router, Bot
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, asc

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id, reset_state
from models.tariff import Tariff
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(Command('tariffs'), StateFilter(None, States.message), UserFilter(check_admin=True, check_root=True))
    async def check_commission(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="shop_ids"
            )

            # Массив тарифов в виде словарей
            visible_tariffs = []

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Получаем все тарифы
                    result = await session.execute(
                        select(Tariff).order_by(asc(Tariff.duration))
                    )
                    tariffs = result.scalars().all()

                    for tariff in tariffs:
                        text = f"<b>Длительность (месяцы):</b> {tariff.duration}\n"
                        text += f"<b>Описание:</b> {tariff.description}\n"
                        text += f"<b>Цена:</b> {tariff.price} руб."

                        m = await send_state_message(
                            state=state,
                            message=message,
                            text=text,
                            parse_mode=ParseMode.HTML,
                            keyboard=kb.create_manage_tariff_keyboard(),
                            state_name="shop_ids"
                        )

                        visible_tariffs.append({
                            'message_id': m.message_id,
                            'tariff': tariff.to_dict(),
                        })

            # Сохраняем массив соответствий message_id и tariff в стейт
            await state.update_data(visible_tariffs=visible_tariffs)

            await send_state_message(
                state=state,
                message=message,
                text="Действия",
                state_name="shop_ids",
                keyboard=kb.create_delete_shop_messages()
            )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.CHANGE_TARIFF_CALLBACK, UserFilter(check_admin=True))
    async def change_fixed_callback(callback_query: types.CallbackQuery, state: FSMContext):
        try:

            # Из стейта получаем visible_tariffs
            data = await state.get_data()

            visible_tariffs = data.get('visible_tariffs')

            # Находим словарь с указанным message_id
            tariff = next((tariff for tariff in visible_tariffs if
                           tariff["message_id"] == callback_query.message.message_id), None)

            if not tariff:
                return

            await state.update_data(current_admin_tariff=tariff['tariff'])

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
            # Получаем введённую цену
            cm = float(message.text)
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Из стейта получаем visible_tariffs
                    data = await state.get_data()

                    tariff_state = data.get('current_admin_tariff')

                    if tariff_state is None or cm < 0:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Ошибка, повторите ввод",
                            state_name="shop_ids"
                        )
                        await state.set_state(States.shop_price)
                        return

                    # Получаем тариф
                    result = await session.execute(
                        select(Tariff).filter(Tariff.id == tariff_state['id'])
                    )
                    tariff = result.scalars().first()

                    if not tariff:
                        return

                    tariff.price = cm

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
