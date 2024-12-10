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

    # Обработчик команды /cities для отображения списка городов (локаций)
    @router.message(Command('cities'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def check_cities(message: types.Message, state: FSMContext):
        try:
            # Сохраняем ID сообщения в состоянии FSM
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="cities_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Получаем список всех добавленных городов из базы данных
                    result = await session.execute(
                        select(City)
                    )
                    cities = result.scalars().all()
                    city_list = ""
                    for i in range(len(cities)):
                        city_list += f"{i + 1}. {cities[i].city}\n"

                    # Формируем текст сообщения с перечислением городов
                    text = f"<b>Список добавленных городов:</b>\n\n{city_list}"

                    if len(cities) == 0:
                        text += "Пусто"

                    # Отправляем сообщение с клавиатурой для управления городами
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

    # Обработчик коллбэка для добавления городов
    @router.callback_query(F.data == callbacks.ADD_CITIES_CALLBACK, UserFilter(check_admin=True))
    async def read_cities_to_add(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            # Запрашиваем у пользователя список городов для добавления
            text = ("<b>Введите название городов через запятую и пробел, пример:</b>\n\nМосква, Казань, Новосибирск, "
                    "Владивосток")
            await send_state_message(
                state=state,
                message=callback_query.message,
                text=text,
                state_name="cities_ids",
                parse_mode=ParseMode.HTML,
            )
            # Устанавливаем состояние для добавления городов
            await state.set_state(States.cities_to_add)
        except Exception as e:
            print(e)

    # Обработчик коллбэка для удаления городов
    @router.callback_query(F.data == callbacks.DELETE_CITIES_CALLBACK, UserFilter(check_admin=True))
    async def read_cities_to_remove(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            # Запрашиваем у пользователя список городов для удаления
            text = ("<b>Введите название городов через запятую и пробел, пример:</b>\n\nМосква, Казань, Новосибирск, "
                    "Владивосток")
            await send_state_message(
                state=state,
                message=callback_query.message,
                text=text,
                state_name="cities_ids",
                parse_mode=ParseMode.HTML,
            )
            # Устанавливаем состояние для удаления городов
            await state.set_state(States.cities_to_remove)
        except Exception as e:
            print(e)

    # Универсальная функция для добавления или удаления городов
    async def mange_cities(action: str, result_text: str, message: types.Message, state: FSMContext):
        # Сохраняем ID сообщения в состоянии FSM
        await add_state_id(
            state=state,
            message_id=message.message_id,
            state_name="cities_ids"
        )
        # Разделяем введённый текст на список городов
        cities = message.text.split(', ')
        if len(cities) == 0:
            # Если список пуст, просим повторить ввод
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
                # Проверяем корректность названия каждого города
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
                    # Добавляем города в базу данных
                    for city_name in cities:
                        city = City(
                            city=city_name,
                        )
                        session.add(city)
                elif action == "remove":
                    # Удаляем города из базы данных
                    for city_name in cities:
                        result = await session.execute(
                            select(City).filter(City.city == city_name)
                        )
                        city = result.scalars().first()

                        if city is not None:
                            await session.delete(city)

            # Сохраняем изменения в базе данных
            await session.commit()

        # Отправляем сообщение о результате операции
        await send_state_message(
            state=state,
            message=message,
            text=result_text,
            keyboard=kb.create_delete_admin_messages_keyboard(),
            state_name="cities_ids"
        )

    # Обработчик состояния для добавления городов
    @router.message(States.cities_to_add, UserFilter(check_admin=True))
    async def read_list_of_cities_to_add(message: types.Message, state: FSMContext):
        try:
            # Вызываем универсальную функцию для добавления городов
            await mange_cities(
                action="add",
                message=message,
                state=state,
                result_text="Города успешно добавлены"
            )
        except Exception as e:
            # Просим повторить ввод
            print(e)
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите ввод",
                state_name="cities_ids"
            )
            await state.set_state(States.cities_to_add)

    # Обработчик состояния для удаления городов
    @router.message(States.cities_to_remove, UserFilter(check_admin=True))
    async def read_list_of_cities_to_remove(message: types.Message, state: FSMContext):
        try:
            # Вызываем универсальную функцию для удаления городов
            await mange_cities(
                action="remove",
                message=message,
                state=state,
                result_text="Города успешно удалены"
            )
        except Exception as e:
            # Просим повторить ввод
            print(e)
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите ввод",
                state_name="cities_ids"
            )
            await state.set_state(States.cities_to_remove)

    dp.include_router(router)
