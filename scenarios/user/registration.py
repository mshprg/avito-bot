import re

from aiogram import Router, Bot, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InputMediaVideo
from sqlalchemy import select

import callbacks
import config
import kb
from db import AsyncSessionLocal
from message_processing import delete_state_messages, send_state_message, add_state_id, send_state_media
from models.city import City
from models.user import User
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()
    from applications import show_applications

    @router.message(F.text, Command('start'))
    async def policy_accept(message: types.Message, state: FSMContext):
        try:
            user_id: int = message.from_user.id
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(User.telegram_user_id == user_id)
                    )
                    user = result.scalars().first()

                    if user is not None:
                        await message.answer(
                            text="|^_^|",
                            reply_markup=kb.create_feedback_keyboard()
                        )
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Вы уже зарегистрированы",
                        )
                        return

                    policy_url = 'https://telegra.ph/Politika-obrabotki-personalnyh-dannyh-07-24-2'
                    agreement_url = 'https://telegra.ph/Polzovatelskoe-soglashenie-07-24-11'

                    text = (
                        f"Нажимая на кнопку <b>Далее</b>, вы соглашаетесь с <a href='{policy_url}'>Политикой "
                        f"обработки персональных данных</a> и <a href='{agreement_url}'>Пользовательским "
                        f"соглашением</a>")

                    media = [
                        InputMediaVideo(
                            media="BAACAgIAAxkBAAJA-mbWIw-8YGxgvsNOPha5JfdhwZ5sAAIeXQACIQ6xSlSHuUJ2GE_uNQQ",
                            caption="Перед регистрацией ознакомьтесь с видео",
                        )
                    ]

                    await send_state_media(
                        state=state,
                        chat_id=message.chat.id,
                        media=media,
                        bot=bot
                    )

                    await send_state_message(
                        state=state,
                        message=message,
                        text=text,
                        parse_mode=ParseMode.HTML,
                        keyboard=kb.create_policy_accept_callback()
                    )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.POLICY_ACCEPT_CALLBACK)
    async def registration_start(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Введите ваше ФИО в формате:\nФамилия Имя Отчество",
            )

            await state.set_state(States.name)
        except Exception as e:
            print(e)

    @router.message(States.name)
    async def read_name(message: types.Message, state: FSMContext):
        try:
            fio = message.text.split(' ')

            await add_state_id(state, message.message_id)

            if len(fio) != 3:
                await send_state_message(
                    state=state,
                    message=message,
                    text="Неверный формат, требуемый формат:\nФамилия Имя Отчество\nВведите ФИО"
                )
                await state.set_state(States.name)
                return

            for text in fio:
                if len(text) < 2:
                    await send_state_message(
                        state=state,
                        message=message,
                        text="Фамилия, Имя или Отчество не может быть менее 2 символов"
                    )
                    await send_state_message(
                        state=state,
                        message=message,
                        text="Введите ваше ФИО в формате:\nФамилия Имя Отчество"
                    )
                    await state.set_state(States.name)
                    return

            await state.update_data(name=message.text)
            await send_state_message(
                state=state,
                message=message,
                text="Введите ваш номер телефона в формате:\n+7XXXXXXXXXX\nПример: +71234567890"
            )
            await state.set_state(States.phone)
        except Exception as e:
            print(e)

    @router.message(States.phone)
    async def read_phone(message: types.Message, state: FSMContext):
        try:
            await add_state_id(state, message.message_id)
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    phone = message.text

                    pattern = r'^\+7\d{10}$'
                    ok = re.match(pattern, phone) is not None

                    if not ok:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Ошибка: неверный формат, повторите ввод"
                        )
                        await state.set_state(States.phone)
                        return

                    result = await session.execute(
                        select(User).filter(User.phone == phone)
                    )
                    user = result.scalars().first()

                    if user is not None:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Аккаунт с таким номером телефона уже зарегистрирован"
                        )
                        return

                    result = await session.execute(
                        select(City)
                    )
                    cities_db = result.scalars().all()
                    cities = [city.city for city in cities_db]

                    await state.update_data(phone=phone)
                    await send_state_message(
                        state=state,
                        message=message,
                        text="Выберите город в котором вы находитесь",
                        keyboard=kb.create_cities_keyboard(cities)
                    )
                    await state.set_state(States.city)
        except Exception as e:
            print(e)

    @router.message(States.city)
    async def read_city(message: types.Message, state: FSMContext):
        try:
            await add_state_id(state, message.message_id)
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    city = message.text
                    result = await session.execute(
                        select(City)
                    )
                    cities_db = result.scalars().all()
                    cities = [city.city for city in cities_db]

                    if city not in cities:
                        if message.from_user.id not in config.ROOT_USER_IDS:
                            await send_state_message(
                                state=state,
                                message=message,
                                text="Данный город не поддерживается\nВыберите город в котором вы находитесь",
                                keyboard=kb.create_cities_keyboard(cities)
                            )
                            await state.set_state(States.city)
                            return
                        else:
                            new_city = City(
                                city=city,
                            )
                            session.add(new_city)

                await session.commit()

            await state.update_data(city=message.text)

            media = [
                InputMediaVideo(media='BAACAgIAAxkBAAIcFmbHzfVmDRjILdprqCvC0qafunmUAAJxTAACRedAStenQseCZodmNQQ'),
                InputMediaVideo(media='BAACAgIAAxkBAAIcF2bHzfVnkMcmL3B6vL0G5ip3oLJFAAJyTAACRedASmeuxIUdxcoMNQQ'),
                InputMediaVideo(media='BAACAgIAAxkBAAIcGGbHzfVI-phdmyBpkLeW3eIdjK0FAAJzTAACRedASv7gevgwIDWFNQQ')
            ]

            await send_state_message(
                state=state,
                message=message,
                text="Видео работы бота:\n",
                keyboard=types.ReplyKeyboardRemove()
            )

            await send_state_media(
                state=state,
                chat_id=message.chat.id,
                media=media,
                bot=bot
            )

            await send_state_message(
                state=state,
                message=message,
                text="<b>Видео помогут ознакомиться с работой бота</b>",
                parse_mode=ParseMode.HTML,
                keyboard=kb.create_show_applications_keyboard()
            )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.SHOW_APPLICATIONS_CALLBACK)
    async def show_application_for_user(callback_query: types.CallbackQuery, state: FSMContext):

        async with AsyncSessionLocal() as session:
            async with session.begin():
                user_data = await state.get_data()

                admin = False
                if callback_query.from_user.id in config.ROOT_USER_IDS:
                    admin = True

                user = User(
                    name=user_data.get("name"),
                    phone=user_data.get("phone"),
                    city=user_data.get("city"),
                    telegram_user_id=callback_query.message.chat.id,
                    telegram_chat_id=callback_query.message.chat.id,
                    admin=admin,
                    in_working=False
                )

                session.add(user)

        await delete_state_messages(
            state=state,
            bot=bot,
            chat_id=callback_query.message.chat.id
        )

        await state.clear()

        await callback_query.message.answer(
            text="|^_^|",
            reply_markup=kb.create_feedback_keyboard()
        )

        await show_applications(
            chat_id=callback_query.message.chat.id,
            user_id=callback_query.message.chat.id,
            bot=bot
        )

    dp.include_router(router)
