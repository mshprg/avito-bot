from aiogram import Router, Bot, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id
from models.city import City
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(Command('cities'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def check_cities(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="cities_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():

                    result = await session.execute(
                        select(City)
                    )
                    cities = result.scalars().all()
                    city_list = ""
                    for i in range(len(cities)):
                        city_list += f"{i + 1}. {cities[i].city}\n"

                    text = f"<b>Список добавленных городов:</b>\n\n{city_list}"

                    if len(cities) == 0:
                        text += "Пусто"

                    await send_state_message(
                        state=state,
                        message=message,
                        text=text,
                        parse_mode=ParseMode.HTML,
                        keyboard=kb.create_manage_cities_keyboard(),
                        state_name="cities_ids"
                    )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.ADD_CITIES_CALLBACK, UserFilter(check_admin=True))
    async def read_cities_to_add(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            text = ("<b>Введите название городов через запятую и пробел, пример:</b>\n\nМосква, Казань, Новосибирск, "
                    "Владивосток")
            await send_state_message(
                state=state,
                message=callback_query.message,
                text=text,
                state_name="cities_ids",
                parse_mode=ParseMode.HTML,
            )
            await state.set_state(States.cities_to_add)
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.DELETE_CITIES_CALLBACK, UserFilter(check_admin=True))
    async def read_cities_to_remove(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            text = ("<b>Введите название городов через запятую и пробел, пример:</b>\n\nМосква, Казань, Новосибирск, "
                    "Владивосток")
            await send_state_message(
                state=state,
                message=callback_query.message,
                text=text,
                state_name="cities_ids",
                parse_mode=ParseMode.HTML,
            )
            await state.set_state(States.cities_to_remove)
        except Exception as e:
            print(e)

    async def mange_cities(action: str, result_text: str, message: types.Message, state: FSMContext):
        await add_state_id(
            state=state,
            message_id=message.message_id,
            state_name="cities_ids"
        )
        cities = message.text.split(', ')
        if len(cities) == 0:
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите ввод",
                state_name="cities_ids"
            )
            await state.set_state(States.cities_to_add)
            return

        for city in cities:
            if len(city) < 2:
                await send_state_message(
                    state=state,
                    message=message,
                    text="Ошибка, повторите ввод",
                    state_name="cities_ids"
                )
                await state.set_state(States.cities_to_add)
                return

        async with AsyncSessionLocal() as session:
            async with session.begin():
                if action == "add":
                    for city_name in cities:
                        city = City(
                            city=city_name,
                        )
                        session.add(city)
                elif action == "remove":
                    for city_name in cities:
                        result = await session.execute(
                            select(City).filter(City.city == city_name)
                        )
                        city = result.scalars().first()

                        if city is not None:
                            await session.delete(city)

            await session.commit()

        await send_state_message(
            state=state,
            message=message,
            text=result_text,
            keyboard=kb.create_delete_admin_messages_keyboard(),
            state_name="cities_ids"
        )

    @router.message(States.cities_to_add, UserFilter(check_admin=True))
    async def read_list_of_cities_to_add(message: types.Message, state: FSMContext):
        try:
            await mange_cities(
                action="add",
                message=message,
                state=state,
                result_text="Города успешно добавлены"
            )
        except Exception as e:
            print(e)
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите ввод",
                state_name="cities_ids"
            )
            await state.set_state(States.cities_to_add)

    @router.message(States.cities_to_remove, UserFilter(check_admin=True))
    async def read_list_of_cities_to_remove(message: types.Message, state: FSMContext):
        try:
            await mange_cities(
                action="remove",
                message=message,
                state=state,
                result_text="Города успешно удалены"
            )
        except Exception as e:
            print(e)
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите ввод",
                state_name="cities_ids"
            )
            await state.set_state(States.cities_to_remove)

    dp.include_router(router)
