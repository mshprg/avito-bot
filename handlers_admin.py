import calendar
import time
from datetime import datetime

from aiogram import Router, Bot, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import callbacks
import kb
import config
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import delete_state_messages, send_state_message, add_state_id
from models.addiction import Addiction
from models.application import Application
from models.city import City
from models.comission import Commission
from models.confirmation import Confirmation
from models.confirmation_addiction import ConfirmationAddiction
from models.feedback import Feedback
from models.item import Item
from models.item_addiction import ItemAddiction
from models.requisites import Requisites
from models.user import User
from states import States


def load_handlers_admin(dp, bot: Bot):
    router = Router()

    async def reset_state(state: FSMContext):
        data = await state.get_data()
        await state.clear()
        await state.update_data(data)

    @router.message(Command('cancel'), StateFilter("*"))
    async def cancel(message: types.Message, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Confirmation).filter(Confirmation.telegram_user_id == message.from_user.id)
                    )
                    confirmation = result.scalars().first()

                    if confirmation is not None:
                        return

                    await reset_state(state)

                    result = await session.execute(
                        select(User).filter(User.telegram_user_id == message.from_user.id)
                    )
                    user = result.scalars().first()

                    if user is None:
                        return

                    if user.in_working:
                        await state.set_state(States.message)

            await bot.delete_message(
                chat_id=message.chat.id,
                message_id=message.message_id
            )
            await bot.send_message(
                chat_id=message.chat.id,
                text="Действие отменено"
            )
        except Exception as e:
            print(e)

    @router.message(Command('reload'), StateFilter(None, States.message))
    async def reload(message: types.Message, state: FSMContext):
        from message_processing import delete_message_ids
        from applications import show_applications, show_messages_for_application
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Confirmation).filter(Confirmation.telegram_user_id == message.from_user.id)
                    )
                    confirmation = result.scalars().first()

                    if confirmation is not None:
                        return

                    await delete_state_messages(
                        state=state,
                        bot=bot,
                        chat_id=message.chat.id
                    )

                    await delete_message_ids(
                        session=session,
                        bot=bot,
                        telegram_chat_id=message.chat.id
                    )

                    result = await session.execute(
                        select(User).filter(User.telegram_chat_id == message.chat.id)
                    )
                    user = result.scalars().first()

                    if user is None:
                        return

                    result = await session.execute(
                        select(Application).filter(Application.working_user_id == user.telegram_user_id)
                    )
                    application = result.scalars().first()

                    result = await session.execute(
                        select(Addiction).filter(
                            Addiction.telegram_chat_id == message.chat.id)
                    )
                    addictions = result.scalars().all()

                    for ad in addictions:
                        try:
                            await bot.delete_message(
                                chat_id=message.chat.id,
                                message_id=ad.telegram_message_id,
                            )
                        except:
                            ...
                        await session.delete(ad)

                    if user.in_working:
                        in_working = True
                        u = {'telegram_chat_id': user.telegram_chat_id}
                        a = {
                            'avito_chat_id': application.avito_chat_id,
                            'user_id': application.user_id,
                            'author_id': application.author_id,
                            'username': application.username
                        }
                    else:
                        in_working = False

            await state.clear()

            if in_working:
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
            else:
                await show_applications(
                    chat_id=message.chat.id,
                    user_id=message.from_user.id,
                    bot=bot
                )
        except Exception as e:
            print(e)

    async def check_user_for_admin(session, state, chat_id):
        result = await session.execute(
            select(User).filter(User.telegram_chat_id == chat_id)
        )
        user = result.scalars().first()

        if user is None:
            return

        if not user.admin and user.telegram_user_id not in config.ROOT_USER_IDS:
            await send_state_message(
                state=state,
                bot=bot,
                chat_id=chat_id,
                text="Вы должны иметь права администратора"
            )
            return False

        return True

    @router.message(Command('admins'), StateFilter(None, States.message))
    async def show_admins(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="admin_ids"
            )
            if message.from_user.id in config.ROOT_USER_IDS:
                async with AsyncSessionLocal() as session:
                    async with session.begin():
                        result = await session.execute(
                            select(User).filter(and_(
                                User.admin == True,
                                User.telegram_chat_id != message.chat.id
                            ))
                        )
                        users = result.scalars().all()

                        if len(users) == 0:
                            await send_state_message(
                                state=state,
                                message=message,
                                text="Пусто",
                                state_name="admin_ids"
                            )
                            return

                        for user in users:
                            text = f"<b>{user.name}\n\n{user.phone}\n\n{user.city}</b>"
                            await send_state_message(
                                state=state,
                                message=message,
                                text=text,
                                parse_mode=ParseMode.HTML,
                                state_name="admin_ids"
                            )

                await send_state_message(
                    state=state,
                    message=message,
                    text="Действия",
                    keyboard=kb.create_delete_admin_messages_keyboard(),
                    state_name="admin_ids"
                )
        except Exception as e:
            print(e)

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

    @router.message(Command('requisites'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def check_requisites(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="requisites_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():

                    result = await session.execute(
                        select(Requisites)
                    )
                    requisites = result.scalars().first()

                    if requisites is not None:
                        card = requisites.card_number

                        text = f"Текущий номер карты: *{card}*"
                        await send_state_message(
                            state=state,
                            message=message,
                            text=text,
                            parse_mode=ParseMode.MARKDOWN_V2,
                            keyboard=kb.create_manage_requisites_keyboard(),
                            state_name="requisites_ids",
                        )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.CHANGE_REQUISITES_CALLBACK, UserFilter(check_admin=True))
    async def change_requisites_callback(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            text = "Введите новый номер карты, пример:\n*0000000000000000*"
            await send_state_message(
                state=state,
                message=callback_query.message,
                text=text,
                state_name="requisites_ids",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            await state.set_state(States.requisites)
        except Exception as e:
            print(e)

    @router.message(States.requisites, UserFilter(check_admin=True))
    async def read_requisites_callback(message: types.Message, state: FSMContext):
        try:
            card_number = int(message.text)
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="requisites_ids"
            )
            if len(message.text) != 16:
                await send_state_message(
                    state=state,
                    message=message,
                    text="Ошибка: неверный формат номера",
                    state_name="requisites_ids"
                )
                await state.set_state(States.requisites)
                return
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Requisites)
                    )
                    requisites = result.scalars().first()

                    string = str(card_number)

                    formatted_string = ' '.join([string[i:i + 4] for i in range(0, len(string), 4)])

                    requisites.card_number = formatted_string

                await session.commit()

            await send_state_message(
                state=state,
                message=message,
                text="Номер карты успешно изменён",
                keyboard=kb.create_delete_admin_messages_keyboard(),
                state_name="requisites_ids"
            )
        except Exception as e:
            print(e)
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите ввод",
                state_name="requisites_ids"
            )
            await state.set_state(States.requisites)

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
                    b = await check_user_for_admin(session=session, state=state, chat_id=message.chat.id)
                    if not b:
                        return

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

    async def change_admin_command_handler(text: str, state_name: str, state_to_set, message: types.Message, state: FSMContext):
        await add_state_id(
            state=state,
            message_id=message.message_id,
            state_name=state_name
        )
        if message.from_user.id in config.ROOT_USER_IDS:
            await send_state_message(
                state=state,
                message=message,
                text=text,
                state_name=state_name
            )
            await state.set_state(state_to_set)
            return True

        return False

    @router.message(Command('mkadmin'), StateFilter(None, States.message))
    async def make_admin(message: types.Message, state: FSMContext):
        try:
            b = await change_admin_command_handler(
                state=state,
                message=message,
                state_name="make_admin_ids",
                state_to_set=States.admin_change,
                text="Введите номер телефона пользователя"
            )
            if b:
                await state.update_data(admin_change="add")
        except Exception as e:
            print(e)

    @router.message(Command('rmadmin'), StateFilter(None, States.message))
    async def delete_admin(message: types.Message, state: FSMContext):
        try:
            b = await change_admin_command_handler(
                state=state,
                message=message,
                state_name="make_admin_ids",
                state_to_set=States.admin_change,
                text="Введите номер телефона пользователя"
            )
            if b:
                await state.update_data(admin_change="remove")
        except Exception as e:
            print(e)

    @router.message(States.admin_change, UserFilter(check_admin=True))
    async def check_admin_phone(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="make_admin_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    phone = message.text
                    result = await session.execute(
                        select(User).filter(User.phone == phone)
                    )
                    user = result.scalars().first()

                    data = await state.get_data()
                    change = data.get("admin_change", None)

                    if change is None:
                        return

                    if user is None:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Такого пользователя не найдено",
                            state_name="make_admin_ids"
                        )
                        return

                    if user.banned:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Ошибка: пользователь заблокирован",
                            keyboard=kb.create_delete_admin_messages_keyboard(),
                            state_name="make_admin_ids"
                        )
                        return

                    text = "Ошибка"
                    if change == "add":
                        user.admin = True
                        text = "Пользователю предоставлены права администратора"
                    elif change == "remove":
                        user.admin = False
                        text = "Пользователь лишён прав администратора"

                    await state.update_data(admin_change="")

                await session.commit()

            await send_state_message(
                state=state,
                message=message,
                text=text,
                keyboard=kb.create_delete_admin_messages_keyboard(),
                state_name="make_admin_ids"
            )
        except Exception as e:
            print(e)
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, введите телефон заново",
                state_name="make_admin_ids"
            )
            await state.set_state(States.admin_change)

    @router.message(Command('report'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def generate_report(message: types.Message, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():

                    result = await session.execute(
                        select(User).filter(User.telegram_user_id == message.from_user.id)
                    )
                    user = result.scalars().first()

                    if user is None:
                        return

                    if not user.admin:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Вы должны иметь права администратора"
                        )
                        return

                    await send_state_message(
                        state=state,
                        message=message,
                        text="Если вы желаете сгенерировать отчёт за день \- введите дату в формате *ДД\.ММ\.ГГГГ*\nЕсли "
                             "вы желаете сгенерировать отчёт за месяц \- введите дату в формате *ММ\.ГГГГ*",
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                    await state.set_state(States.report_date)
        except Exception as e:
            print(e)

    @router.message(States.report_date, UserFilter(check_admin=True))
    async def read_report_date(message: types.Message, state: FSMContext):
        from report import collect_data
        try:
            date_str = message.text

            start_unix, end_unix = None, None

            try:
                date_obj = datetime.strptime(date_str, '%m.%Y')

                start_of_month = datetime(date_obj.year, date_obj.month, 1)
                start_unix = int(time.mktime(start_of_month.timetuple()))

                _, last_day = calendar.monthrange(date_obj.year, date_obj.month)
                end_of_month = datetime(date_obj.year, date_obj.month, last_day, 23, 59, 59)
                end_unix = int(time.mktime(end_of_month.timetuple()))
            except ValueError:
                pass

            try:
                date_obj = datetime.strptime(date_str, '%d.%m.%Y')

                start_of_day = datetime(date_obj.year, date_obj.month, date_obj.day)
                start_unix = int(time.mktime(start_of_day.timetuple()))

                end_of_day = datetime(date_obj.year, date_obj.month, date_obj.day, 23, 59, 59)
                end_unix = int(time.mktime(end_of_day.timetuple()))
            except ValueError:
                pass

            if start_unix is not None and end_unix is not None:
                async with AsyncSessionLocal() as session:
                    async with session.begin():

                        report = await collect_data(session, start_unix, end_unix)

                        if report:
                            await bot.send_media_group(
                                chat_id=message.chat.id,
                                media=[report]
                            )
                        else:
                            await bot.send_message(
                                chat_id=message.chat.id,
                                text="За данный период нет новых заявок"
                            )

            await reset_state(state)

        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.DELETE_MESSAGES_CALLBACK)
    async def delete_admin_messages(callback_query: types.CallbackQuery, state: FSMContext):
        state_ids = ["admin_ids", "commission_ids", "requisites_ids", "cities_ids", "make_admin_ids", "report_ids",
                     "location_ids", "feedback_ids", "feedback_admin_ids", "confirmation_admin_ids", "ban_ids"]
        try:
            for state_name in state_ids:
                data = await state.get_data()
                ids = data.get(state_name, [])
                if callback_query.message.message_id in ids:
                    if state_name == "feedback_admin_ids":
                        await state.update_data(visible_feedbacks={})
                    elif state_name == "confirmation_admin_ids":
                        await state.update_data(visible_confirmations={})
                    await delete_state_messages(
                        state=state,
                        bot=bot,
                        chat_id=callback_query.message.chat.id,
                        state_name=state_name,
                    )
                    await reset_state(state)

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(User.telegram_chat_id == callback_query.message.chat.id)
                    )
                    user = result.scalars().first()

                    if user is None:
                        return

                    if user.in_working:
                        await state.set_state(States.message)
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.ADD_CITY_TO_ITEM_CALLBACK, UserFilter(check_admin=True))
    async def add_location_to_item(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            current_state = await state.get_state()
            await state.update_data(previous_state=current_state)
            await add_state_id(
                state=state,
                message_id=callback_query.message.message_id,
                state_name="location_ids"
            )
            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Введите локации через запятую, например:\nМосква, Московская область",
                state_name="location_ids"
            )
            await state.update_data(add_location=[callback_query.message.message_id, callback_query.message.chat.id])
            await state.set_state(States.add_location)
        except Exception as e:
            print(e)

    @router.message(States.add_location, UserFilter(check_admin=True))
    async def read_locations(message: types.Message, state: FSMContext):
        from applications import show_application
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="location_ids"
            )
            locations = message.text
            if locations is None or len(locations) == 0:
                await send_state_message(
                    state=state,
                    message=message,
                    text="Ошибка, повторите ввод",
                    state_name="location_ids"
                )
                await state.set_state(States.add_location)
                return
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    data = await state.get_data()
                    data = data.get("add_location", [1, 1])
                    result = await session.execute(
                        select(ItemAddiction).filter(and_(
                            ItemAddiction.telegram_message_id == data[0],
                            ItemAddiction.telegram_chat_id == data[1]
                        ))
                    )
                    item_addiction = result.scalars().first()

                    if item_addiction is None:
                        return

                    result = await session.execute(
                        select(Item).filter(Item.id == item_addiction.item_id)
                    )
                    item = result.scalars().first()

                    if item is None:
                        return

                    result = await session.execute(
                        select(Application).filter(Application.item_id == item.avito_item_id)
                    )
                    applications = result.scalars().all()

                    item.location = locations
                    for ap in applications:
                        ap.item_location = locations

                    result = await session.execute(
                        select(User).filter(
                            User.in_working == False
                        )
                    )
                    users = result.scalars().all()

                    result = await session.execute(
                        select(ItemAddiction).filter(ItemAddiction.item_id == item.id)
                    )
                    item_addictions = result.scalars().all()

                    for ad in item_addictions:
                        try:
                            await bot.delete_message(
                                chat_id=ad.telegram_chat_id,
                                message_id=ad.telegram_message_id,
                            )
                        except:
                            ...
                        await session.delete(ad)

                    await session.flush()

                    for user in users:
                        for ap in applications:
                            await show_application(
                                session=session,
                                application=ap,
                                user_city=user.city,
                                is_admin=user.admin,
                                bot=bot,
                                chat_id=user.telegram_chat_id
                            )

                await session.commit()

            await send_state_message(
                state=state,
                message=message,
                text="Локация успешно добавлена",
                state_name="location_ids",
                keyboard=kb.create_delete_admin_messages_keyboard()
            )

            data = await state.get_data()
            previous_state = data.get('previous_state')

            if previous_state:
                await state.set_state(previous_state)

        except Exception as e:
            print(e)

    @router.message(Command('items'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def get_none_items(message: types.Message):
        try:
            from applications import show_new_item_for_admin
            async with AsyncSessionLocal() as session:
                async with session.begin():

                    result = await session.execute(
                        select(Item).filter(
                            Item.location == "None"
                        )
                    )
                    items = result.scalars().all()

                    if len(items) == 0:
                        await bot.send_message(
                            chat_id=message.chat.id,
                            text="Нет новых объявлений"
                        )
                        return

                    for item in items:
                        await show_new_item_for_admin(
                            session=session,
                            bot=bot,
                            url=item.url,
                            item_id=item.id,
                            avito_item_id=item.avito_item_id,
                            chat_id=message.chat.id
                        )
        except Exception as e:
            print(e)

    async def manage_questions_improvements(message: types.Message, state: FSMContext, non_feedback_text, action_text, type_feedback):
        await add_state_id(
            state=state,
            message_id=message.message_id,
            state_name="feedback_admin_ids"
        )
        async with AsyncSessionLocal() as session:
            async with session.begin():

                result = await session.execute(
                    select(Feedback).filter(and_(
                        Feedback.type == type_feedback,
                        Feedback.answer == ""
                    ))
                )
                feedbacks = result.scalars().all()

                if len(feedbacks) == 0:
                    await send_state_message(
                        state=state,
                        message=message,
                        text=non_feedback_text,
                        state_name="feedback_admin_ids",
                        keyboard=kb.create_delete_admin_messages_keyboard()
                    )
                    return

                messages = []
                for feedback in feedbacks:
                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == feedback.telegram_user_id
                        )
                    )
                    user = result.scalars().first()

                    if user:
                        name = user.name
                    else:
                        name = "неизвестный пользователь"

                    text = f"<b>{action_text} {name}</b>\n\n{feedback.text}"
                    m = await send_state_message(
                        state=state,
                        message=message,
                        text=text,
                        keyboard=kb.create_answer_feedback_keyboard(),
                        parse_mode=ParseMode.HTML,
                        state_name="feedback_admin_ids",
                    )

                    messages.append({
                        'message_id': m.message_id,
                        'feedback': feedback.to_dict()
                    })

                state_feedback = {
                    'messages': messages,
                    'current_feedback': None,
                }

                await state.update_data(visible_feedbacks=state_feedback)

        await send_state_message(
            state=state,
            message=message,
            text="Действия",
            keyboard=kb.create_delete_admin_messages_keyboard(),
            state_name="feedback_admin_ids",
        )

    @router.message(Command('questions'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def get_feedback(message: types.Message, state: FSMContext):
        try:
            await manage_questions_improvements(
                message=message,
                state=state,
                non_feedback_text="Нет неотвеченных вопросов",
                action_text="Спрашивает",
                type_feedback="question"
            )
        except Exception as e:
            print(e)

    @router.message(Command('improvements'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def get_improvements(message: types.Message, state: FSMContext):
        try:
            await manage_questions_improvements(
                message=message,
                state=state,
                non_feedback_text="Нет предложений по улучшению",
                action_text="Предлагает",
                type_feedback="improvement"
            )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.ANSWER_QUESTION_CALLBACK, UserFilter(check_admin=True))
    async def answer_question_callback(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            data = await state.get_data()
            state_feedback: dict = data.get("visible_feedbacks", {})
            messages = state_feedback.get("messages", [])

            feedback = None
            for m in messages:
                if m['message_id'] == callback_query.message.message_id:
                    feedback = m['feedback']

            if feedback is None:
                print("Error")
                return

            state_feedback['current_feedback'] = feedback

            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Введите ответ",
                state_name="feedback_admin_ids",
            )

            await state.update_data(visible_feedbacks=state_feedback)

            await state.set_state(States.visible_feedbacks)

        except Exception as e:
            print(e)

    @router.message(States.visible_feedbacks, UserFilter(check_admin=True))
    async def read_answer(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="feedback_admin_ids"
            )

            data = await state.get_data()
            state_feedback: dict = data.get("visible_feedbacks", {})
            feedback = state_feedback.get("current_feedback", None)

            if feedback is None:
                print("Error")
                return

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Feedback).filter(
                            Feedback.id == feedback['id']
                        )
                    )
                    feedback = result.scalars().first()

                    feedback.answer = message.text

                await session.commit()

            await send_state_message(
                state=state,
                message=message,
                text="Ответ сохранён",
                keyboard=kb.create_delete_admin_messages_keyboard(),
                state_name="feedback_admin_ids",
            )

            state_feedback['current_feedback'] = None
            await state.update_data(visible_feedbacks=state_feedback)
        except Exception as e:
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, введите текст заново",
                state_name="feedback_admin_ids",
            )
            await state.set_state(States.visible_feedbacks)
            print(e)

    @router.message(Command("confirmations"), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def get_confirmations(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="confirmation_admin_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Confirmation)
                    )
                    confirmations = result.scalars().all()

                    if len(confirmations) == 0:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Переводов не найдено",
                            keyboard=kb.create_delete_admin_messages_keyboard(),
                            state_name="confirmation_admin_ids",
                        )
                        return

                    user_ids = [c.telegram_user_id for c in confirmations]
                    result = await session.execute(
                        select(User).filter(User.telegram_user_id.in_(user_ids))
                    )
                    users = result.scalars().all()
                    d = {}

                    for u in users:
                        d[u.telegram_user_id] = u

                    visible_confirmations = []
                    for c in confirmations:
                        text = (f"<b>Подтверждение от пользователя {d[c.telegram_user_id].name}</b>\nНомер телефона: "
                                f"{d[c.telegram_user_id].phone}\nКод: <b>{c.telegram_user_id}</b>\nСумма: <b>{c.amount}</b>")
                        m = await send_state_message(
                            state=state,
                            message=message,
                            text=text,
                            parse_mode=ParseMode.HTML,
                            keyboard=kb.create_list_confirmations_keyboard(),
                            state_name="confirmation_admin_ids",
                        )
                        visible_confirmations.append({
                            'message_id': m.message_id,
                            'confirmation': c.to_dict()
                        })

                    await state.update_data(visible_confirmations=visible_confirmations)

                    await send_state_message(
                        state=state,
                        message=message,
                        text="Действия",
                        keyboard=kb.create_delete_admin_messages_keyboard(),
                        state_name="confirmation_admin_ids",
                    )

                await session.commit()

        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.APPROVED_CONF_CALLBACK, UserFilter(check_admin=True))
    async def approved_confirmation_callback(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    conf = None
                    data = await state.get_data()
                    visible_confirmations = data.get("visible_confirmations", [])

                    for c in visible_confirmations:
                        if c['message_id'] == callback_query.message.message_id:
                            conf = c['confirmation']

                    if conf is None:
                        result = await session.execute(
                            select(ConfirmationAddiction).filter(and_(
                                ConfirmationAddiction.telegram_chat_id == callback_query.message.chat.id,
                                ConfirmationAddiction.telegram_message_id == callback_query.message.message_id,
                            ))
                        )
                        conf_addiction = result.scalars().first()
                        result = await session.execute(
                            select(Confirmation).filter(Confirmation.id == conf_addiction.confirmation_id)
                        )
                    else:
                        result = await session.execute(
                            select(Confirmation).filter(Confirmation.id == conf['id'])
                        )
                    confirmation = result.scalars().first()

                    if confirmation is None:
                        return

                    if confirmation.type == "open":
                        text = "Оплата подтверждена"
                        await bot.edit_message_text(
                            chat_id=confirmation.telegram_user_id,
                            message_id=confirmation.telegram_message_id,
                            text=text,
                            reply_markup=kb.create_confirmation_keyboard()
                        )
                    elif confirmation.type == "close":
                        text = "Оплата подтверждена"
                        await bot.edit_message_text(
                            chat_id=confirmation.telegram_user_id,
                            message_id=confirmation.telegram_message_id,
                            text=text,
                            reply_markup=kb.create_close_application_keyboard()
                        )

                    result = await session.execute(
                        select(ConfirmationAddiction).filter(ConfirmationAddiction.confirmation_id == confirmation.id)
                    )
                    conf_addictions = result.scalars().all()

                    await bot.delete_message(
                        chat_id=callback_query.message.chat.id,
                        message_id=callback_query.message.message_id
                    )

                    for ca in conf_addictions:
                        try:
                            await bot.delete_message(
                                chat_id=ca.telegram_chat_id,
                                message_id=ca.telegram_message_id
                            )
                            await session.delete(ca)
                        except:
                            ...

                    await session.delete(confirmation)

                await session.commit()
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.DELETE_CONF_CALLBACK)
    async def delete_conf_message(callback_query: types.CallbackQuery):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(ConfirmationAddiction).filter(and_(
                            ConfirmationAddiction.telegram_chat_id == callback_query.message.chat.id,
                            ConfirmationAddiction.telegram_message_id == callback_query.message.message_id,
                        ))
                    )
                    conf_addiction = result.scalars().first()

                    if conf_addiction:
                        await session.delete(conf_addiction)

                    try:
                        await bot.delete_message(
                            chat_id=callback_query.message.chat.id,
                            message_id=callback_query.message.message_id
                        )
                    except:
                        ...

                await session.commit()
        except Exception as e:
            print(e)

    async def ban_command_handler(message: types.Message, state: FSMContext, setting_state):
        await add_state_id(
            state=state,
            message_id=message.message_id,
            state_name="ban_ids"
        )
        await send_state_message(
            state=state,
            message=message,
            text="Введите номер телефона пользователя",
            state_name="ban_ids"
        )
        await state.set_state(setting_state)

    @router.message(Command('ban'), UserFilter(check_admin=True))
    async def ban_user(message: types.Message, state: FSMContext):
        try:
            await ban_command_handler(message, state, States.ban)
        except Exception as e:
            print(e)

    @router.message(Command('unban'), UserFilter(check_admin=True))
    async def unban_user(message: types.Message, state: FSMContext):
        try:
            await ban_command_handler(message, state, States.unban)
        except Exception as e:
            print(e)

    @router.message(States.ban, UserFilter(check_admin=True))
    async def read_ban_number(message: types.Message, state: FSMContext):
        from applications import show_application
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="ban_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    phone = message.text
                    result = await session.execute(
                        select(User).filter(User.phone == phone)
                    )
                    user = result.scalars().first()

                    if user is None:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Пользователя с таким номером телефона не существует",
                            state_name="ban_ids"
                        )
                        await state.set_state(States.ban)
                        return

                    if message.from_user.id in config.ROOT_USER_IDS:
                        if user.telegram_user_id not in config.ROOT_USER_IDS:
                            if user.admin:
                                user.admin = False
                            user.banned = True
                        else:
                            await send_state_message(
                                state=state,
                                message=message,
                                text="У вас недостаточно прав для блокировки этого пользователя",
                                keyboard=kb.create_delete_admin_messages_keyboard(),
                                state_name="ban_ids",
                            )
                    else:
                        if user.telegram_user_id not in config.ROOT_USER_IDS and not user.admin:
                            user.banned = True
                        else:
                            await send_state_message(
                                state=state,
                                message=message,
                                text="У вас недостаточно прав для блокировки этого пользователя",
                                keyboard=kb.create_delete_admin_messages_keyboard(),
                                state_name="ban_ids",
                            )

                    await session.flush()

                    if user.banned and user.in_working:
                        result = await session.execute(
                            select(Application).filter(and_(
                                Application.working_user_id == user.telegram_user_id,
                                Application.in_working == True,
                            ))
                        )
                        application = result.scalars().first()

                        if application:
                            application.in_working = False
                            application.working_user_id = -1
                            application.pay_type = "None"
                            application.com_value = 0
                            user.in_working = False

                            result = await session.execute(
                                select(User).filter(and_(
                                    User.in_working == False,
                                    User.banned == False,
                                ))
                            )
                            users = result.scalars().all()

                            for u in users:
                                await show_application(
                                    session=session,
                                    is_admin=u.admin,
                                    application=application,
                                    user_city=u.city,
                                    bot=bot,
                                    chat_id=u.telegram_chat_id
                                )

                    if user.banned:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Пользователь заблокирован",
                            keyboard=kb.create_delete_admin_messages_keyboard(),
                            state_name="ban_ids",
                        )

                await session.commit()
        except Exception as e:
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите попытку",
                state_name="ban_ids"
            )
            await state.set_state(States.ban)
            print(e)

    @router.message(States.unban, UserFilter(check_admin=True))
    async def read_unban_number(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="ban_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    phone = message.text
                    result = await session.execute(
                        select(User).filter(User.phone == phone)
                    )
                    user = result.scalars().first()

                    if user is None:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Пользователя с таким номером телефона не существует",
                            state_name="ban_ids"
                        )
                        await state.set_state(States.unban)
                        return

                    user.banned = False

                    await send_state_message(
                        state=state,
                        message=message,
                        text="Пользователь разблокирован",
                        keyboard=kb.create_delete_admin_messages_keyboard(),
                        state_name="ban_ids",
                    )

                await session.commit()
        except Exception as e:
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, повторите попытку",
                state_name="ban_ids"
            )
            await state.set_state(States.ban)
            print(e)

    dp.include_router(router)
