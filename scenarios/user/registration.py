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

    # Считываем команду /start
    @router.message(F.text, Command('start'))
    async def policy_accept(message: types.Message, state: FSMContext):
        try:
            user_id: int = message.from_user.id
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Получаем юзера по его telegram_user_id
                    result = await session.execute(
                        select(User).filter(User.telegram_user_id == user_id)
                    )
                    user = result.scalars().first()

                    # Если юзер сущетвует, то не регистриуем его
                    if user is not None:
                        # Выводим сообщение с клавиатурой
                        await message.answer(
                            text="|^_^|",
                            reply_markup=kb.create_feedback_keyboard()
                        )
                        # Отправляем сообщение
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Вы уже зарегистрированы",
                        )
                        return

                    # Ссылка на политику обработки персональных данных
                    policy_url = 'https://telegra.ph/Politika-obrabotki-personalnyh-dannyh-07-24-2'
                    # Ссылка на пользовательское соглашение
                    agreement_url = 'https://telegra.ph/Polzovatelskoe-soglashenie-07-24-11'

                    # Генерируем текст
                    text = (
                        f"Нажимая на кнопку <b>Далее</b>, вы соглашаетесь с <a href='{policy_url}'>Политикой "
                        f"обработки персональных данных</a> и <a href='{agreement_url}'>Пользовательским "
                        f"соглашением</a>")

                    # Создаем медиа для видео-инструкции
                    media = [
                        InputMediaVideo(
                            media="BAACAgIAAxkBAAJmZGb5sz9S0VK2SKRlBsMN7Uq-k18UAAJBXAACToTQSzeguoXgZte9NgQ",
                            caption="Перед регистрацией ознакомьтесь с видео",
                        )
                    ]

                    # Отправляем видео
                    await send_state_media(
                        state=state,
                        chat_id=message.chat.id,
                        media=media,
                        bot=bot
                    )

                    # Отправляем сообщение с клавиатурой
                    await send_state_message(
                        state=state,
                        message=message,
                        text=text,
                        parse_mode=ParseMode.HTML,
                        keyboard=kb.create_policy_accept_callback()
                    )
        except Exception as e:
            print(e)

    # Обработчик нажатия кнопки "Далее"
    @router.callback_query(F.data == callbacks.POLICY_ACCEPT_CALLBACK)
    async def registration_start(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            # Просим ввести ФИО
            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Введите ваше ФИО в формате:\nФамилия Имя Отчество",
            )

            # Ожидаем ФИО
            await state.set_state(States.name)
        except Exception as e:
            print(e)

    # Ожидаем ввод ФИО
    @router.message(States.name)
    async def read_name(message: types.Message, state: FSMContext):
        try:
            # Получаем ФИО и делим на 3 части
            fio = message.text.split(' ')

            # Добавляем id сообщения в массив id
            await add_state_id(state, message.message_id)

            # Длина ФИО обязательно 3 слова
            if len(fio) != 3:
                await send_state_message(
                    state=state,
                    message=message,
                    text="Неверный формат, требуемый формат:\nФамилия Имя Отчество\nВведите ФИО"
                )
                await state.set_state(States.name)
                return

            for text in fio:
                # Каждая часть ФИОН обязательно не меньше 2ух символов
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

            # Обновляем данные ФИО в стейте
            await state.update_data(name=message.text)
            # Просим ввести номер телефона
            await send_state_message(
                state=state,
                message=message,
                text="Введите ваш номер телефона в формате:\n+7XXXXXXXXXX\nПример: +71234567890\n<b>Мы пришлем код на "
                     "этот номер</b>",
                parse_mode=ParseMode.HTML,
            )
            # Ожидаем номер телефона
            await state.set_state(States.phone)
        except Exception as e:
            print(e)

    # Ожидаем ввод номера телефона
    @router.message(States.phone)
    async def read_phone(message: types.Message, state: FSMContext):
        try:
            # Добавляем id сообщения в массив id
            await add_state_id(state, message.message_id)

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Получаем текст номера
                    phone = message.text

                    # Проверяем соответствие номера формату
                    pattern = r'^\+7\d{10}$'
                    ok = re.match(pattern, phone) is not None

                    # Если не соответствует, то просим повторить ввод
                    if not ok:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Ошибка: неверный формат, повторите ввод"
                        )
                        await state.set_state(States.phone)
                        return

                    # Ищем пользователей с таким же номером
                    result = await session.execute(
                        select(User).filter(User.phone == phone)
                    )
                    user = result.scalars().first()

                    # Если есть такие пользователя, то сообщаем об этом
                    if user is not None:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Аккаунт с таким номером телефона уже зарегистрирован, введите другой номер"
                        )
                        await state.set_state(States.phone)
                        return

                    # Проверяем, создавались ли коды для этого номера
                    result = await session.execute(
                        select(Code).filter(and_(
                            Code.telegram_user_id == message.from_user.id,
                            Code.code_type == "phone"
                        ))
                    )
                    code_db = result.scalars().first()

                    # Если был такой, то удаляем его
                    if code_db:
                        await session.delete(code_db)

                    # Генерируем цифры кода
                    random_code = random.randint(100000, 999999)

                    # Добавляем их в сообщение
                    sms_text = f'Код регистрации для "Заявка легко": {random_code}'

                    api = SmsAero(config.SMSAERO_EMAIL, config.SMSAERO_API_KEY)
                    try:
                        # Отсылаем их на нужный номер телефона
                        await api.send_sms(int(phone.replace("+", "")), sms_text)
                    except:
                        # Если возникла ошибка, то сообщаем об этом
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Мы не можем отправить код на данный номер телефона, введите друой номер или "
                                 "попробуйте позже",
                        )
                        await state.set_state(States.phone)
                        await session.close()
                        return

                    # Добавляем код в базу данных
                    code = Code(
                        telegram_user_id=message.from_user.id,
                        code=random_code,
                        created=int(time.time() * 1000),
                        code_type="phone"
                    )

                    session.add(code)

                    # Обновляем данные в стейте
                    await state.update_data(phone=phone)

                    # Просим ввести отправленный код, или предлагаем ввести другой номер телефона
                    await send_state_message(
                        state=state,
                        message=message,
                        text="На номер телефона был отпрален код подтверждения, введите код",
                        keyboard=kb.create_repeat_phone_keyboard()
                    )

                    # Ожидаем ввод кода
                    await state.set_state(States.phone_code)

            await session.commit()
        except Exception as e:
            print(e)

    # Пользователь решил ввести другой номер (по нажатию кнопки)
    @router.callback_query(F.data == callbacks.REPEAT_PHONE_CALLBACK)
    async def repeat_phone(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Находим созданный код для данного юзера
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

                        # Если данный код был создан меньше минуты назад, то просим юзера подождать
                        if time_diff < time_delay * 1000:
                            await send_state_message(
                                state=state,
                                message=callback_query.message,
                                text=f"Мы отправили вам код менее 1 минуты назад, подождите ещё "
                                     f"{time_delay - int(time_diff / 1000)} сек. и повторите попытку",
                            )
                            await session.close()
                            return

            # Заново просим номер телефона
            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Введите ваш номер телефона в формате:\n+7XXXXXXXXXX\nПример: +71234567890\n<b>Мы пришлем код на "
                     "этот номер</b>",
                parse_mode=ParseMode.HTML,
            )
            # Удаляем предыдущее сообщение с запросом номер
            try:
                await bot.delete_message(
                    chat_id=callback_query.message.chat.id,
                    message_id=callback_query.message.message_id,
                )
            except:
                pass

            # Ожидаем номер телефона
            await state.set_state(States.phone)
        except Exception as e:
            print(e)

    # Ожидаем ввода кода подтверждения
    @router.message(States.phone_code)
    async def read_code(message: types.Message, state: FSMContext):
        try:
            # Считывем текст
            code = message.text

            # Добавляем id сообщения в массив id
            await add_state_id(state, message.message_id)

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Ищем код пользователя в бд
                    result = await session.execute(
                        select(Code).filter(and_(
                            Code.telegram_user_id == message.chat.id,
                            Code.code_type == "phone"
                        ))
                    )
                    code_db = result.scalars().first()

                    # Проверяем совпадение
                    if str(code_db.code) != code:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Неверный код, повторите ввод или используйте другой номер телефона",
                            keyboard=kb.create_repeat_phone_keyboard()
                        )
                        await state.set_state(States.phone_code)
                        return

                    # Удаляем код в бд
                    await session.delete(code_db)

                    # Получаем все доступные города из бд
                    result = await session.execute(
                        select(City)
                    )
                    cities_db = result.scalars().all()
                    cities = [city.city for city in cities_db]

                    # Отправляем сообщение с клавиатурой-списком городов
                    await send_state_message(
                        state=state,
                        message=message,
                        text="Выберите город в котором вы находитесь",
                        keyboard=kb.create_cities_keyboard(cities)
                    )

                    # Ожидаем ввод города
                    await state.set_state(States.city)
        except Exception as e:
            print(e)

    # Ожидаем выбора города пользователя
    @router.message(States.city)
    async def read_city(message: types.Message, state: FSMContext):
        try:
            # Добавляем id сообщения в массив id
            await add_state_id(state, message.message_id)

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Считывем текст
                    city = message.text

                    # Получаем все доступные города из бд
                    result = await session.execute(
                        select(City)
                    )
                    cities_db = result.scalars().all()
                    cities = [city.city for city in cities_db]

                    # Проверяем есть ли введённый город в массиве доступных
                    if city not in cities:
                        # Если пользователь не коренной админ
                        if message.from_user.id not in config.ROOT_USER_IDS:
                            # Сообщаем о том что город не поддерживается
                            await send_state_message(
                                state=state,
                                message=message,
                                text="Данный город не поддерживается\nВыберите город в котором вы находитесь",
                                keyboard=kb.create_cities_keyboard(cities)
                            )
                            await state.set_state(States.city)
                            return
                        else:
                            # Создаем новый доступный город в бд
                            new_city = City(
                                city=city,
                            )
                            session.add(new_city)

                await session.commit()

            # Обновляем данные в стейте
            await state.update_data(city=message.text)

            # Генерируем сообщение
            text = ('У вас активрован пробный период работы: 3 дня. После истечения этого срока потребуется приобрести '
                    'доступ к заявкам, используйте кнопку "Информация о подписке" на клавиатуре')

            # Отправляем сообщение с кнопкой
            await send_state_message(
                state=state,
                message=message,
                text=text,
                parse_mode=ParseMode.HTML,
                keyboard=kb.create_show_applications_keyboard()
            )
        except Exception as e:
            print(e)

    # Обработчик кнопки "Показать заявки" и регистрация юзера
    @router.callback_query(F.data == callbacks.SHOW_APPLICATIONS_CALLBACK)
    async def show_application_for_user(callback_query: types.CallbackQuery, state: FSMContext):

        async with AsyncSessionLocal() as session:
            async with session.begin():
                # Получаем все данные из стейта
                user_data = await state.get_data()

                admin = False
                # Если Tg ID юзера есть в массиве id коренных админов, то устанавливаем admin = True
                if callback_query.from_user.id in config.ROOT_USER_IDS:
                    admin = True

                # Создаем юзера
                user = User(
                    name=user_data.get("name"),
                    phone=user_data.get("phone"),
                    city=user_data.get("city"),
                    telegram_user_id=callback_query.message.chat.id,
                    telegram_chat_id=callback_query.message.chat.id,
                    admin=admin,
                    in_working=False,
                    created=int(time.time() * 1000)
                )

                end_time = int(time.time() * 1000) + 86400000 * 3

                # Создаем для него подписку на тариф с пробным периодом
                subscription = Subscription(
                    telegram_user_id=callback_query.message.chat.id,
                    duration=0,
                    end_time=end_time,
                    description='Пробный период на 3 дня'
                )

                session.add(subscription)
                session.add(user)

            await session.commit()

        # Удаляем все сообщения по id в стейте
        await delete_state_messages(
            state=state,
            bot=bot,
            chat_id=callback_query.message.chat.id
        )

        await state.clear()

        # Отправляем собщение с инлайн клавиатурой с действиями
        await callback_query.message.answer(
            text="|^_^|",
            reply_markup=kb.create_feedback_keyboard()
        )

        # Показываем пользователю все доступные заявки
        await show_applications(
            chat_id=callback_query.message.chat.id,
            user_id=callback_query.message.chat.id,
            bot=bot
        )

    dp.include_router(router)
