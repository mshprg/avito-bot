from asyncio import sleep

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

    # Обработчик команды /sending для начала процесса рассылки
    # Доступен только администраторам, если пользователь не находится в другом состоянии FSM
    @router.message(F.text, Command('sending'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def load_sending(message: types.Message, state: FSMContext):
        try:
            # Добавляем идентификатор состояния для отслеживания сообщений
            await add_state_id(
                state=state,
                state_name="sending_ids",
                message_id=message.message_id
            )

            # Отправляем сообщение с инструкцией ввести текст для рассылки
            await send_state_message(
                message=message,
                text="Введите текст рассылки",
                state=state,
                state_name="sending_ids"
            )
            # Устанавливаем новое состояние FSM
            await state.set_state(States.sending_text)
        except Exception as e:
            print(e)

    # Обработчик для ввода текста рассылки
    # Проверяет, что пользователь — администратор, и сохраняет текст сообщения
    @router.message(States.sending_text, UserFilter(check_admin=True))
    async def read_sending_text(message: types.Message, state: FSMContext):
        try:
            # Добавляем идентификатор состояния для отслеживания сообщений
            await add_state_id(
                state=state,
                state_name="sending_ids",
                message_id=message.message_id
            )

            # Получаем текст сообщения
            text = message.text

            if text is None:
                raise Exception("Invalid text")

            # Форматируем текст сообщения с указанием, что это сообщение от администратора
            text = "<b>Сообщение от администратора:</b>\n" + text

            # Сохраняем текст в данных состояния
            await state.update_data(sending_text=text)

            # Отправляем пользователю выбор способа рассылки
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
            print(e)

    # Обработчик для отправки сообщения всем пользователям
    # Проверяет, что пользователь — администратор, и выполняет рассылку
    @router.callback_query(F.data == callbacks.SEND_MESSAGE_ALL_CALLBACK, UserFilter(check_admin=True))
    async def send_message_for_all_users(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            # Извлекаем список всех пользователей, кроме инициатора рассылки и заблокированных
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

            # Извлекаем текст рассылки из состояния
            data = await state.get_data()
            sending_text = data.get("sending_text", "")

            if len(sending_text) == 0:
                raise Exception("Invalid text")

            # Отправляем сообщение каждому пользователю с небольшой задержкой
            for chat_id in chat_ids:
                try:
                    await sleep(0.3)
                    await bot.send_message(
                        chat_id=chat_id,
                        text=sending_text,
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    print(e)
                    await sleep(1)

            # Уведомляем администратора об успешной рассылке
            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Сообщение отправлено",
                keyboard=kb.create_delete_admin_messages_keyboard(),
                state_name="sending_ids"
            )

            # Сбрасываем состояние FSM
            await reset_state(state=state)
        except Exception as e:
            print(e)

    # Обработчик для выбора города перед отправкой сообщения
    # Загружает список всех доступных локаций
    @router.callback_query(F.data == callbacks.SELECT_SENDING_CITY_CALLBACK, UserFilter(check_admin=True))
    async def select_sending_city(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            # Извлекаем список всех городов из базы данных
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(City)
                    )
                    cities_db = result.scalars().all()

                    # Формируем текст со списком доступных городов
                    text = "<b>Введите назавания локаций через запятую и пробел, вот списко всех локаций:</b>\n"

                    for i, city in enumerate(cities_db, start=1):
                        text += f"{i}. {city.city}\n"

                    # Отправляем текст пользователю
                    await send_state_message(
                        state=state,
                        message=callback_query.message,
                        parse_mode=ParseMode.HTML,
                        text=text
                    )
                    # Устанавливаем состояние для выбора локаций
                    await state.set_state(States.sending_locations)
        except Exception as e:
            print(e)

    # Обработчик для чтения выбранных локаций и отправки сообщения только пользователям в этих городах
    @router.message(States.sending_locations, UserFilter(check_admin=True))
    async def read_sending_locations(message: types.Message, state: FSMContext):
        try:
            # Добавляем идентификатор состояния для отслеживания сообщений
            await add_state_id(
                state=state,
                state_name="sending_ids",
                message_id=message.message_id
            )

            # Получаем текст с введёнными локациями
            text = message.text

            if text is None:
                raise Exception("Invalid text")

            # Извлекаем текст рассылки из состояния
            data = await state.get_data()
            sending_text = data.get("sending_text", "")

            if len(sending_text) == 0:
                raise Exception("Invalid text")

            # Разделяем локации на список
            locations = text.split(", ")

            # Извлекаем пользователей, которые находятся в указанных локациях
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

            # Отправляем сообщение каждому пользователю с небольшой задержкой
            for chat_id in chat_ids:
                try:
                    await sleep(0.3)
                    await bot.send_message(
                        chat_id=chat_id,
                        text=sending_text,
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    print(e)
                    await sleep(1)

            # Уведомляем администратора об успешной рассылке
            await send_state_message(
                state=state,
                message=message,
                text="Сообщение отправлено",
                state_name="sending_ids",
                keyboard=kb.create_delete_admin_messages_keyboard()
            )

            # Сбрасываем состояние FSM
            await reset_state(state=state)
        except Exception as e:
            print(e)

    dp.include_router(router)
