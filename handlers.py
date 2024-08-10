import io
import re
import time
from time import sleep
from aiogram import Router, types, F, Bot
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InputMediaPhoto
from sqlalchemy import select, and_
import callbacks
import kb
import s3_cloud
from applications import show_applications, show_messages_for_application, send_message_for_application, \
    show_application
import config
from db import AsyncSessionLocal
from filters import UserFilter
from models.addiction import Addiction
from models.application import Application
from models.city import City
from models.comission import Commission
from models.confirmation import Confirmation
from models.feedback import Feedback
from models.image import Image
from models.mask import Mask
from models.requisites import Requisites
from models.user import User
from states import States
from message_processing import send_state_message, delete_state_messages, add_state_id, delete_message_ids

media_groups = {}


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(Command('myimprovements'), StateFilter(None, States.message), UserFilter())
    async def get_my_improvements(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="feedback_ids",
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Feedback).filter(and_(
                            Feedback.telegram_user_id == message.from_user.id,
                            Feedback.type == "improvement"
                        ))
                    )
                    feedbacks = result.scalars().all()

                    if len(feedbacks) == 0:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Вы не пердлагали улучшений",
                            keyboard=kb.create_clear_feedback_keyboard(),
                            state_name="feedback_ids",
                        )
                        return

                    for feedback in feedbacks:
                        answer = "Пока нет ответа" if len(feedback.answer) == 0 else feedback.answer
                        text = f"<b>Ваше предложение</b>:\n{feedback.text}\n\n<b>Комментарий администратора:</b>\n{answer}"
                        await send_state_message(
                            state=state,
                            message=message,
                            text=text,
                            parse_mode=ParseMode.HTML,
                            state_name="feedback_ids",
                        )

                    await send_state_message(
                        state=state,
                        message=message,
                        text="Действия",
                        keyboard=kb.create_clear_feedback_keyboard(),
                        state_name="feedback_ids",
                    )
        except Exception as e:
            print(e)

    @router.message(Command('myquestions'), StateFilter(None, States.message), UserFilter())
    async def get_my_questions(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="feedback_ids",
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Feedback).filter(and_(
                            Feedback.telegram_user_id == message.from_user.id,
                            Feedback.type == "question"
                        ))
                    )
                    feedbacks = result.scalars().all()

                    if len(feedbacks) == 0:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Вы не задавали вопросов",
                            keyboard=kb.create_clear_feedback_keyboard(),
                            state_name="feedback_ids",
                        )
                        return

                    for feedback in feedbacks:
                        answer = "Пока нет ответа" if len(feedback.answer) == 0 else feedback.answer
                        text = f"<b>Ваш вопрос</b>:\n{feedback.text}\n\n<b>Ответ от администратора:</b>\n{answer}"
                        await send_state_message(
                            state=state,
                            message=message,
                            text=text,
                            parse_mode=ParseMode.HTML,
                            state_name="feedback_ids",
                        )

                    await send_state_message(
                        state=state,
                        message=message,
                        text="Действия",
                        keyboard=kb.create_clear_feedback_keyboard(),
                        state_name="feedback_ids",
                    )
        except Exception as e:
            print(e)

    @router.message(F.text, Command('start'))
    async def registration_user(message: types.Message, state: FSMContext):
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

                    await send_state_message(
                        state=state,
                        message=message,
                        text="Введите ваше ФИО в формате:\nФамилия Имя Отчество"
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

            policy_url = 'https://telegra.ph/Politika-obrabotki-personalnyh-dannyh-07-24-2'
            agreement_url = 'https://telegra.ph/Polzovatelskoe-soglashenie-07-24-11'

            text = (f"Нажимая на кнопку <b>Показать заявки</b>, вы соглашаетесь с <a href='{policy_url}'>Политикой "
                    f"обработки персональных данных</a> и <a href='{agreement_url}'>Пользовательским "
                    f"соглашением</a>\n<b>Видео поможет ознакомиться с работой бота</b>")

            await send_state_message(
                state=state,
                message=message,
                text="Ознакомительное видео:",
                keyboard=types.ReplyKeyboardRemove()
            )

            await send_state_message(
                state=state,
                message=message,
                text=text,
                parse_mode=ParseMode.HTML,
                keyboard=kb.create_video_keyboard()
            )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.WATCHED_VIDEO_CALLBACK)
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

    @router.message(F.text == "Обратная связь", UserFilter())
    async def send_feedback_callback(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="feedback_ids"
            )
            await send_state_message(
                state=state,
                message=message,
                text="*Действия:*",
                parse_mode=ParseMode.MARKDOWN_V2,
                keyboard=kb.create_feedback_actions_keyboard(),
                state_name="feedback_ids"
            )
        except Exception as e:
            print(e)

    async def send_feedback_message(text, type_feedback, callback_query: types.CallbackQuery, state: FSMContext):
        try:
            await send_state_message(
                state=state,
                message=callback_query.message,
                text=text,
                state_name="feedback_ids",
            )

            await state.update_data(feedback=type_feedback)
            await state.set_state(States.feedback)
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.SEND_QUESTION_CALLBACK, UserFilter())
    async def send_question_callback(callback_query: types.CallbackQuery, state: FSMContext):
        await send_feedback_message(
            text="Отправьте вопрос",
            type_feedback="question",
            callback_query=callback_query,
            state=state
        )

    @router.callback_query(F.data == callbacks.SEND_IMPROVEMENT_CALLBACK, UserFilter())
    async def send_improvement_callback(callback_query: types.CallbackQuery, state: FSMContext):
        await send_feedback_message(
            text="Предложите улучшение",
            type_feedback="improvement",
            callback_query=callback_query,
            state=state
        )

    @router.message(States.feedback)
    async def read_feedback(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="feedback_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    user_data = await state.get_data()
                    type_feedback = user_data.get("feedback", "None")
                    feedback = Feedback(
                        type=type_feedback,
                        text=message.text,
                        telegram_user_id=message.from_user.id
                    )

                    session.add(feedback)

                await session.commit()

            await send_state_message(
                state=state,
                message=message,
                text="Запрос отправлен",
                keyboard=kb.create_clear_feedback_keyboard(),
                state_name="feedback_ids",
            )
        except Exception as e:
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, введите текст заново",
                state_name="feedback_ids",
            )
            await state.set_state(States.feedback)
            print(e)

    @router.callback_query(F.data == callbacks.TAKE_APPLICATION_CALLBACK, UserFilter())
    async def select_application(callback_query: types.CallbackQuery):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_message_id == callback_query.message.message_id)
                    )
                    addiction = result.scalars().first()

                    if addiction is None:
                        await bot.delete_messages(
                            chat_id=callback_query.message.chat.id,
                            message_ids=[callback_query.message.message_id],
                        )
                        return

                    result = await session.execute(
                        select(Application).filter(
                            Application.id == addiction.application_id)
                    )
                    application = result.scalars().first()

                    if application is None or application.in_working and application.waiting_confirmation:
                        await bot.send_message(
                            text="Данную зявку уже взяли",
                            chat_id=callback_query.message.chat.id
                        )
                        return

                    result = await session.execute(
                        select(Commission)
                    )
                    commission = result.scalars().first()

                    text = (
                        "*Выберите способ оплаты комиссии:*\n_Фиксированная комиссия_ \- платите сразу\n_Процент от "
                        "стоимости_ \- платите процент от стоимости заказа")

                    await bot.edit_message_text(
                        text=text,
                        chat_id=callback_query.message.chat.id,
                        message_id=callback_query.message.message_id,
                        reply_markup=kb.create_price_keyboard(commission.percent, commission.fixed),
                        parse_mode=ParseMode.MARKDOWN_V2,
                    )

        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.SELECT_FIXED_CALLBACK, UserFilter())
    async def wait_paid(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_message_id == callback_query.message.message_id)
                    )
                    addiction = result.scalars().first()

                    if addiction is None:
                        await bot.delete_messages(
                            chat_id=callback_query.message.chat.id,
                            message_ids=[callback_query.message.message_id],
                        )

                    result = await session.execute(
                        select(Application).filter(
                            Application.id == addiction.application_id)
                    )
                    application = result.scalars().first()

                    if application is None or application.in_working or application.waiting_confirmation:
                        await bot.send_message(
                            text="Данную зявку уже взяли",
                            chat_id=callback_query.message.chat.id
                        )
                        return

                    result = await session.execute(
                        select(Requisites)
                    )
                    requisites = result.scalars().first()

                    result = await session.execute(
                        select(Commission)
                    )
                    commission = result.scalars().first()

                    text = (f"*Требуется оплатить комиссию:*\n\nНомер карты \- *{requisites.card_number}*\nCумма оплаты: "
                            f"*{commission.fixed}* руб\nВ сообщении к переводу укажите номер: *{callback_query.from_user.id}*")

                    await bot.edit_message_text(
                        text=text,
                        chat_id=callback_query.message.chat.id,
                        message_id=callback_query.message.message_id,
                        reply_markup=kb.create_paid_fixed_callback(),
                        parse_mode=ParseMode.MARKDOWN_V2,
                    )

                    await state.update_data(pay_type="fixed")

                await session.commit()

        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.PAID_FIXED_CALLBACK, UserFilter())
    async def paid_fixed_callback(callback_query: types.CallbackQuery):
        from applications import show_confirmation_for_admins
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    text = ("<b>НЕ УДАЛЯЙТЕ ЭТО СООБЩЕНИЕ</b>\nВы сможете открыть заявку как только администратор "
                            "подтвердит перевод")

                    await bot.edit_message_text(
                        chat_id=callback_query.message.chat.id,
                        message_id=callback_query.message.message_id,
                        text=text,
                        parse_mode=ParseMode.HTML,
                    )

                    result = await session.execute(
                        select(Commission)
                    )
                    commission = result.scalars().first()

                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == callback_query.from_user.id)
                    )
                    user = result.scalars().first()
                    user.in_working = True

                    confirmation = Confirmation(
                        telegram_user_id=callback_query.from_user.id,
                        telegram_message_id=callback_query.message.message_id,
                        amount=commission.fixed,
                        created=round(time.time() * 1000),
                        type="open"
                    )
                    session.add(confirmation)
                    await session.flush()

                    result = await session.execute(
                        select(Addiction).filter(and_(
                            Addiction.telegram_message_id == callback_query.message.message_id,
                            Addiction.telegram_chat_id == callback_query.message.chat.id
                        ))
                    )
                    user_addiction = result.scalars().first()

                    result = await session.execute(
                        select(Application).filter(
                            Application.id == user_addiction.application_id)
                    )
                    application = result.scalars().first()

                    application.waiting_confirmation = True

                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.application_id == user_addiction.application_id)
                    )
                    app_addictions = result.scalars().all()

                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_chat_id == callback_query.message.chat.id)
                    )
                    current_user_addictions = result.scalars().all()

                    for ad in app_addictions:
                        if ad.telegram_message_id != callback_query.message.message_id:
                            try:
                                await bot.delete_message(
                                    chat_id=ad.telegram_chat_id,
                                    message_id=ad.telegram_message_id,
                                )
                            except:
                                ...
                            await session.delete(ad)

                    for ad in current_user_addictions:
                        if ad.telegram_message_id != callback_query.message.message_id:
                            try:
                                await bot.delete_message(
                                    chat_id=ad.telegram_chat_id,
                                    message_id=ad.telegram_message_id,
                                )
                            except:
                                ...
                            await session.delete(ad)

                    await show_confirmation_for_admins(
                        session=session,
                        confirmation=confirmation,
                        author_user=user,
                        bot=bot
                    )

                await session.commit()
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.OPEN_APPLICATION_CALLBACK, UserFilter())
    async def set_application(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            u, a = None, None
            async with AsyncSessionLocal() as session:
                async with session.begin():

                    data = await state.get_data()
                    pay_type = data.get("pay_type")

                    if pay_type is None:
                        await state.update_data(pay_type="percent")
                        pay_type = "percent"

                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == callback_query.from_user.id)
                    )
                    user = result.scalars().first()

                    result = await session.execute(
                        select(Commission)
                    )
                    commission = result.scalars().first()

                    if user is None:
                        return

                    if user.admin:
                        pay_type = "admin"

                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_message_id == callback_query.message.message_id)
                    )
                    addiction = result.scalars().first()

                    if addiction is None:
                        await bot.delete_messages(
                            chat_id=callback_query.message.chat.id,
                            message_ids=[callback_query.message.message_id],
                        )

                    result = await session.execute(
                        select(Application).filter(
                            Application.id == addiction.application_id)
                    )
                    application = result.scalars().first()

                    application.waiting_confirmation = False
                    application.in_working = True
                    application.working_user_id = callback_query.from_user.id
                    application.pay_type = pay_type
                    if pay_type == "percent":
                        application.com_value = commission.percent
                    elif pay_type == "fixed":
                        application.com_value = commission.fixed

                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.application_id == application.id)
                    )
                    addictions = result.scalars().all()

                    for ad in addictions:
                        try:
                            await bot.delete_message(
                                chat_id=ad.telegram_chat_id,
                                message_id=ad.telegram_message_id,
                            )
                        except:
                            ...
                        await session.delete(ad)

                    await session.flush()

                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_chat_id == user.telegram_chat_id)
                    )
                    current_user_addictions = result.scalars().all()

                    for ad in current_user_addictions:
                        try:
                            await bot.delete_message(
                                chat_id=ad.telegram_chat_id,
                                message_id=ad.telegram_message_id,
                            )
                        except:
                            ...
                        await session.delete(ad)

                    u = {'telegram_chat_id': user.telegram_chat_id}
                    a = {
                        'avito_chat_id': application.avito_chat_id,
                        'user_id': application.user_id,
                        'author_id': application.author_id,
                        'username': application.username
                    }

                await session.commit()

            await state.clear()

            await show_messages_for_application(
                state=state,
                bot=bot,
                telegram_chat_id=u['telegram_chat_id'],
                avito_chat_id=a['avito_chat_id'],
                avito_user_id=a['user_id'],
                author_id=a['author_id'],
                username=a['username']
            )

            await state.set_state(States.message)
        except Exception as e:
            print(e)

    @router.message(States.message, UserFilter())
    async def send_message(message: types.Message, state: FSMContext):
        try:
            if message.media_group_id or message.photo or message.video:
                await bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                )
                await state.set_state(States.message)
                return

            text = message.text

            await add_state_id(state, message.message_id)

            data = await state.get_data()
            avito_info = data.get("avito_info", None)

            if avito_info is None:
                async with AsyncSessionLocal() as session:
                    async with session.begin():
                        result = await session.execute(
                            select(Application).filter(and_(
                                Application.working_user_id == message.from_user.id,
                                Application.in_working == True
                            ))
                        )
                        application = result.scalars().first()

                        avito_chat_id = str(application.avito_chat_id)
                        avito_user_id = str(application.user_id)

                        await state.update_data(avito_info={
                            'chat_id': avito_chat_id,
                            'user_id': avito_user_id,
                        })
            else:
                avito_chat_id = avito_info['chat_id']
                avito_user_id = avito_info['user_id']

            await send_message_for_application(
                avito_user_id=avito_user_id,
                avito_chat_id=avito_chat_id,
                text=text,
            )
        except Exception as e:
            print(e)
            await state.set_state(States.message)

    @router.callback_query(F.data == callbacks.STOP_APPLICATION_CALLBACK, UserFilter())
    async def stop_application(callback_query: types.CallbackQuery):
        try:
            text = "<b>Вы уверены что хотите отказаться от заявки?</b>"

            await bot.edit_message_text(
                text=text,
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                reply_markup=kb.create_stop_application_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.FINISH_APPLICATION_CALLBACK, UserFilter())
    async def finish_application(callback_query: types.CallbackQuery):
        try:
            text = ("<b>Вы уверены что хотите завершить работу по заявке?</b>\nПосле подтверждения вам потребуется "
                    "отправить в этот чат заполненную расписпку о получении денег и сумму которую вам заплатили.\n"
                    "Если вы выбрали оплату комиссии в процентах от стоимости заказа, то вам потребуется отправить нам "
                    "эту сумму после завершения заявки, мы сами рассчитаем сумму оплаты")

            await bot.edit_message_text(
                text=text,
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                reply_markup=kb.create_finish_application_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.BACK_TO_APPLICATION_CALLBACK, UserFilter())
    async def back_to_application(callback_query: types.CallbackQuery):
        try:
            text = (
                "*Дествия с зявкой:*\n_Завершить работу_ \- работа по зявке полностью выполнена, оплата получена\n_Отказаться "
                "от заявки_ \- отказ от работы с заявкой, вы больше не сможете взять эту заявку")

            await bot.edit_message_text(
                text=text,
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                reply_markup=kb.create_application_actions_keyboard(),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.EXACTLY_FINISH_CALLBACK, UserFilter())
    async def exactly_finish_application(callback_query: types.CallbackQuery, state: FSMContext):
        global media_groups
        try:
            media_groups.pop(callback_query.from_user.id, None)
            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Отправьте нам заполненную расписку о получении денег, принимаются только изображения"
            )

            await state.set_state(States.finish_files)
        except Exception as e:
            print(e)

    @router.message(States.finish_files, UserFilter())
    async def read_finish_file(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id
            )
            if message.photo is None:
                await send_state_message(
                    state=state,
                    message=message,
                    text="<b>Ошибка</b>\nОтправьте нам заполненную расписку о получении денег, <b>принимаются только "
                         "изображения</b>",
                    parse_mode=ParseMode.HTML,
                )
                await state.set_state(States.finish_files)
                return

            if message.from_user.id not in media_groups:
                media_groups[message.from_user.id] = []

            media_groups[message.from_user.id].append(message.photo.pop())

            if len(media_groups[message.from_user.id]) == 1:
                await send_state_message(
                    state=state,
                    message=message,
                    text="Теперь отправьте нам сумму, которую вы получили за работу (отправьте только число)"
                )

            await state.set_state(States.finish_price)
        except Exception as e:
            await send_state_message(
                state=state,
                message=message,
                text="<b>Ошибка</b>\nОтправьте нам заполненную расписку о получении денег, <b>принимаются только "
                     "изображения</b>",
                parse_mode=ParseMode.HTML,
            )
            await state.set_state(States.finish_files)
            media_groups.pop(message.from_user.id, None)
            print(e)

    async def load_photos(user_id):
        media = media_groups[user_id]

        for photo in media:
            file_info = await bot.get_file(photo.file_id)
            file_bytes = await bot.download_file(file_info.file_path)
            image_bytes = file_bytes.read()
            file_name = s3_cloud.save_file_on_cloud(io.BytesIO(image_bytes))
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Application).filter(and_(
                            Application.working_user_id == user_id,
                            Application.in_working == False,
                        ))
                    )
                    application = result.scalars().first()
                    image = Image(
                        application_id=application.id,
                        file_name=file_name,
                    )
                    session.add(image)

                await session.commit()

        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    select(User).filter(User.admin == True)
                )
                users = result.scalars().all()

                result = await session.execute(
                    select(User).filter(User.telegram_user_id == user_id)
                )
                user = result.scalars().first()

                media_to_send = []

                caption = f"Фото от пользователя {user.name}\nНомер телефона: {user.phone}"

                for m in media:
                    media_to_send.append(
                        InputMediaPhoto(media=m.file_id, caption=caption))

                if media_to_send:
                    for u in users:
                        if u.telegram_user_id != user_id:
                            await bot.send_media_group(chat_id=u.telegram_chat_id, media=media_to_send)

        media_groups.pop(user_id, None)

    @router.message(States.finish_price, UserFilter())
    async def read_finish_price(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    price = int(message.text)

                    result = await session.execute(
                        select(Application).filter(and_(
                            Application.working_user_id == message.from_user.id,
                            Application.in_working == True,
                        ))
                    )
                    application = result.scalars().first()

                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == message.from_user.id)
                    )
                    user = result.scalars().first()

                    if application.pay_type == "percent":
                        p = application.com_value
                        to_pay = round((p / 100) * price, 2)
                        result = await session.execute(
                            select(Requisites)
                        )
                        requisites = result.scalars().first()
                        text = (f"Вы выбрали оплату в процентах от стоимости заказа,\nк оплате <b>{to_pay} руб.</b"
                                f">\nНомер карты - <b>{requisites.card_number}</b>\nНажмите на кнопку после того как "
                                f"перевели нужную сумму\nВ сообщении к <b>обязательно</b> укажите код: <b>"
                                f"{user.telegram_user_id}</b>"),
                        await send_state_message(
                            state=state,
                            message=message,
                            text=text[0],
                            parse_mode=ParseMode.HTML,
                            keyboard=kb.create_paid_comm_keyboard(),
                        )
                        await state.update_data(finish_price=price)
                        return

                    application.price = str(price - application.com_value)
                    application.income += application.com_value
                    application.in_working = False
                    user.in_working = False

                    await delete_message_ids(
                        session=session,
                        bot=bot,
                        telegram_chat_id=user.telegram_chat_id
                    )

                await session.commit()

            await load_photos(message.from_user.id)

            await send_state_message(
                state=state,
                message=message,
                text="Благодарим за работу, скоро появиться список новых заявок"
            )

            sleep(3)

            await delete_state_messages(
                state=state,
                bot=bot,
                chat_id=message.chat.id
            )

            await state.clear()

            await show_applications(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                bot=bot
            )
        except Exception as e:
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите отправку"
            )
            await state.set_state(States.finish_price)
            print(e)

    @router.callback_query(F.data == callbacks.EXACTLY_STOP_CALLBACK, UserFilter())
    async def exactly_stop_application(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == callback_query.message.chat.id)
                    )
                    user = result.scalars().first()

                    result = await session.execute(
                        select(User).filter(User.in_working == False)
                    )
                    other_users = result.scalars().all()

                    result = await session.execute(
                        select(Application).filter(and_(
                            Application.working_user_id == callback_query.message.chat.id,
                            Application.in_working == True,
                        ))
                    )
                    application = result.scalars().first()

                    if application.pay_type == "fixed":
                        await send_state_message(
                            state=state,
                            message=callback_query.message,
                            text="Отправьте номер карты на которую вам нужно вернуть комиссию",
                        )
                        await state.set_state(States.user_card_number)
                        return

                    mask = Mask(
                        application_id=application.id,
                        user_id=user.id,
                        telegram_user_id=callback_query.from_user.id,
                    )
                    session.add(mask)

                    application.in_working = False
                    application.working_user_id = -1
                    application.pay_type = "None"
                    application.com_value = 0
                    user.in_working = False

                    for u in other_users:
                        if u.telegram_chat_id != callback_query.message.chat.id:
                            await show_application(
                                session=session,
                                application=application,
                                bot=bot,
                                chat_id=u.telegram_chat_id,
                                user_city=u.city,
                                is_admin=u.admin
                            )

                    await delete_message_ids(
                        session=session,
                        bot=bot,
                        telegram_chat_id=callback_query.message.chat.id
                    )

                await session.commit()

            await delete_state_messages(
                state=state,
                bot=bot,
                chat_id=callback_query.message.chat.id
            )

            await state.clear()

            await show_applications(
                chat_id=callback_query.message.chat.id,
                user_id=callback_query.from_user.id,
                bot=bot
            )
        except Exception as e:
            print(e)

    @router.message(States.user_card_number, UserFilter())
    async def read_user_card_number(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id
            )
            number = int(message.text)
            if len(message.text) != 16:
                raise Exception("Invalid length")
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == message.from_user.id)
                    )
                    user = result.scalars().first()

                    result = await session.execute(
                        select(User).filter(User.in_working == False)
                    )
                    other_users = result.scalars().all()

                    result = await session.execute(
                        select(Application).filter(and_(
                            Application.working_user_id == message.chat.id,
                            Application.in_working == True,
                        ))
                    )
                    application = result.scalars().first()

                    result = await session.execute(
                        select(User).filter(User.admin == True)
                    )
                    admin_users = result.scalars().all()

                    for u in admin_users:
                        try:
                            text = (f"Пользователь отменил заявку, требуется вернуть комиссию в размере "
                                    f"<b>{int(application.com_value) / 2} руб.</b> на карту <b>{number}</b>")
                            await bot.send_message(
                                chat_id=u.telegram_chat_id,
                                text=text,
                                parse_mode=ParseMode.HTML,
                            )
                        except:
                            ...

                    mask = Mask(
                        application_id=application.id,
                        user_id=user.id,
                        telegram_user_id=message.from_user.id,
                    )
                    session.add(mask)

                    application.in_working = False
                    application.working_user_id = -1
                    application.pay_type = "None"
                    application.income += int(application.com_value) / 2
                    application.com_value = 0
                    user.in_working = False

                    for u in other_users:
                        if u.telegram_chat_id != message.chat.id:
                            await show_application(
                                session=session,
                                application=application,
                                bot=bot,
                                chat_id=u.telegram_chat_id,
                                user_city=u.city,
                                is_admin=u.admin
                            )

                    await delete_message_ids(
                        session=session,
                        bot=bot,
                        telegram_chat_id=message.chat.id
                    )

                await session.commit()

            await delete_state_messages(
                state=state,
                bot=bot,
                chat_id=message.chat.id
            )

            await state.clear()

            await show_applications(
                chat_id=message.chat.id,
                user_id=message.chat.id,
                bot=bot
            )
        except Exception as e:
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите ввод",
            )
            await state.set_state(States.user_card_number)
            print(e)

    @router.callback_query(F.data == callbacks.PAID_COMM_CALLBACK, UserFilter())
    async def paid_commission(callback_query: types.CallbackQuery, state: FSMContext):
        from applications import show_confirmation_for_admins
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == callback_query.from_user.id)
                    )
                    user = result.scalars().first()

                    result = await session.execute(
                        select(Application).filter(and_(
                            Application.working_user_id == callback_query.message.chat.id,
                            Application.in_working == True,
                        ))
                    )
                    application = result.scalars().first()

                    data = await state.get_data()
                    price = data.get("finish_price")
                    ids = data.get("ids", [])

                    if len(ids) >= 2:
                        try:
                            await bot.delete_message(
                                chat_id=callback_query.message.chat.id,
                                message_id=ids[1]
                            )
                        except:
                            ...

                    p = int(application.com_value)
                    to_pay = round((p / 100) * int(price), 2)
                    confirmation = Confirmation(
                        telegram_user_id=user.telegram_user_id,
                        telegram_message_id=callback_query.message.message_id,
                        amount=int(to_pay),
                        created=round(time.time() * 1000),
                        type="close",
                    )
                    session.add(confirmation)
                    await session.flush()

                    text = ("<b>НЕ УДАЛЯЙТЕ ЭТО СООБЩЕНИЕ</b>\nВы сможете закрыть заявку как только администратор "
                            "подтвердит перевод")

                    await bot.edit_message_text(
                        chat_id=callback_query.message.chat.id,
                        message_id=callback_query.message.message_id,
                        text=text,
                        parse_mode=ParseMode.HTML,
                    )

                    await show_confirmation_for_admins(
                        session=session,
                        confirmation=confirmation,
                        author_user=user,
                        bot=bot
                    )

                await session.commit()
        except Exception as e:
            print(e)

    dp.include_router(router)

    @router.callback_query(F.data == callbacks.CLOSE_APPLICATION_CALLBACK, UserFilter())
    async def close_application_callback(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == callback_query.from_user.id)
                    )
                    user = result.scalars().first()

                    result = await session.execute(
                        select(Application).filter(and_(
                            Application.working_user_id == callback_query.message.chat.id,
                            Application.in_working == True,
                        ))
                    )
                    application = result.scalars().first()

                    data = await state.get_data()
                    price = data.get("finish_price")

                    p = int(application.com_value)
                    to_pay = round((p / 100) * price, 2)

                    application.in_working = False
                    application.price = str(price - to_pay)
                    application.income += to_pay
                    user.in_working = False

                await session.commit()

            await load_photos(callback_query.from_user.id)

            await send_state_message(
                state=state,
                bot=bot,
                text="Благодарим за работу, сейчас появиться список новых заявок",
                chat_id=callback_query.message.chat.id
            )

            sleep(3)

            await delete_state_messages(
                state=state,
                bot=bot,
                chat_id=callback_query.message.chat.id
            )

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await delete_message_ids(
                        session=session,
                        bot=bot,
                        telegram_chat_id=callback_query.message.chat.id
                    )

                await session.commit()

            await state.clear()

            await show_applications(
                chat_id=callback_query.message.chat.id,
                user_id=callback_query.from_user.id,
                bot=bot
            )

        except Exception as e:
            print(e)
