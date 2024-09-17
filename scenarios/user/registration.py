import random
import re
import time

from aiogram import Router, Bot, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InputMediaVideo
from smsaero import SmsAero
from sqlalchemy import select, and_

import callbacks
import config
import kb
from db import AsyncSessionLocal
from message_processing import delete_state_messages, send_state_message, add_state_id, send_state_media
from models.city import City
from models.code import Code
from models.subscription import Subscription
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
                text="Введите ваш номер телефона в формате:\n+7XXXXXXXXXX\nПример: +71234567890\n<b>Мы пришлем код на "
                     "этот номер</b>",
                parse_mode=ParseMode.HTML,
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
                        select(Code).filter(and_(
                            Code.telegram_user_id == message.from_user.id,
                            Code.code_type == "phone"
                        ))
                    )
                    code_db = result.scalars().first()

                    if code_db:
                        await session.delete(code_db)

                    random_code = random.randint(100000, 999999)

                    sms_text = f'Код регистрации для "Заявка легко": {random_code}'

                    api = SmsAero(config.SMSAERO_EMAIL, config.SMSAERO_API_KEY)
                    try:
                        ...
                        # await api.send_sms(int(phone.replace("+", "")), sms_text)
                    except:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Мы не можем отправить код на данный номер телефона, введите друой номер",
                        )
                        await state.set_state(States.phone)
                        await session.close()
                        return

                    code = Code(
                        telegram_user_id=message.from_user.id,
                        code=random_code,
                        created=int(time.time() * 1000),
                        code_type="phone"
                    )

                    session.add(code)

                    await state.update_data(phone=phone)

                    await send_state_message(
                        state=state,
                        message=message,
                        text="На номер телефона был отпрален код подтверждения, введите код",
                        keyboard=kb.create_repeat_phone_keyboard()
                    )

                    await state.set_state(States.phone_code)

            await session.commit()
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.REPEAT_PHONE_CALLBACK)
    async def repeat_phone(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Code).filter(and_(
                            Code.telegram_user_id == callback_query.message.chat.id,
                            Code.code_type == "phone"
                        ))
                    )
                    code_db = result.scalars().first()

                    if code_db:
                        code_created = code_db.created

                        time_now = int(time.time() * 1000)

                        time_diff = time_now - code_created
                        time_delay = 60

                        if time_diff < time_delay * 1000:
                            await send_state_message(
                                state=state,
                                message=callback_query.message,
                                text=f"Мы отправили вам код менее 1 минуты назад, подождите ещё "
                                     f"{time_delay - int(time_diff / 1000)} сек. и повторите попытку",
                            )
                            await session.close()
                            return

            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Введите ваш номер телефона в формате:\n+7XXXXXXXXXX\nПример: +71234567890\n<b>Мы пришлем код на "
                     "этот номер</b>",
                parse_mode=ParseMode.HTML,
            )
            try:
                await bot.delete_message(
                    chat_id=callback_query.message.chat.id,
                    message_id=callback_query.message.message_id,
                )
            except:
                pass
            await state.set_state(States.phone)
        except Exception as e:
            print(e)

    @router.message(States.phone_code)
    async def read_code(message: types.Message, state: FSMContext):
        try:
            code = message.text
            await add_state_id(state, message.message_id)
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Code).filter(and_(
                            Code.telegram_user_id == message.chat.id,
                            Code.code_type == "phone"
                        ))
                    )
                    code_db = result.scalars().first()

                    if str(code_db.code) != code:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Неверный код, повторите ввод или используйте другой номер телефона",
                            keyboard=kb.create_repeat_phone_keyboard()
                        )
                        await state.set_state(States.phone_code)
                        return

                    await session.delete(code_db)

                    result = await session.execute(
                        select(City)
                    )
                    cities_db = result.scalars().all()
                    cities = [city.city for city in cities_db]

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

            text = ('У вас активрован пробный период работы: 3 дня. После истечения этого срока потребуется приобрести '
                    'доступ к заявкам, используйте кнопку "Информация о подписке" на клавиатуре')

            await send_state_message(
                state=state,
                message=message,
                text=text,
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
                    in_working=False,
                )

                end_time = int(time.time() * 1000) + 86400000 * 3

                subscription = Subscription(
                    telegram_user_id=callback_query.message.chat.id,
                    status=3,
                    end_time=end_time,
                )

                session.add(subscription)
                session.add(user)

            await session.commit()

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
