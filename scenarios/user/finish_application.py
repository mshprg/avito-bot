import io
import time
from time import sleep

from aiogram import Router, Bot, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import InputMediaPhoto
from sqlalchemy import and_, select

import callbacks
import kb
import s3_cloud
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import delete_message_ids, delete_state_messages, send_state_message, add_state_id
from models.application import Application
from models.confirmation import Confirmation
from models.image import Image
from models.requisites import Requisites
from models.user import User
from states import States

media_groups = {}


def load_handlers(dp, bot: Bot):
    router = Router()
    from applications import show_applications

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
                "*Дествия с зявкой:*\n_Завершить работу_ \- работа по зявке полностью выполнена, оплата получена\n"
                "_Отказаться от заявки_ \- отказ от работы с заявкой, вы больше не сможете взять эту заявку")

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
                    select(Application).filter(and_(
                        Application.working_user_id == user_id,
                        Application.in_working == False,
                    ))
                )
                application = result.scalars().first()

                result = await session.execute(
                    select(User).filter(User.telegram_user_id == user_id)
                )
                user = result.scalars().first()

                media_to_send = []

                if application.pay_type == "percent":
                    user_income = round(application.price * (100 - application.com_value) / 100, 2)
                else:
                    user_income = application.price - application.com_value
                comm = application.price - user_income

                caption = (f"Фото от пользователя {user.name}\nНомер телефона: "
                           f"{user.phone}\nОплата за работу: {application.price} руб.\n"
                           f"Исполнитель получил с учетом комиссии: {user_income} руб.\n"
                           f"Комиссия: {comm} руб.\n"
                           f"Заработано на заявке за всё время: {application.income} руб.")

                for m in media:
                    media_to_send.append(
                        InputMediaPhoto(media=m.file_id, caption=caption))

                if media_to_send:
                    for u in users:
                        if u.telegram_user_id != user_id:
                            sleep(0.1)
                            try:
                                await bot.send_media_group(chat_id=u.telegram_chat_id, media=media_to_send)
                            except Exception as e:
                                print(e)

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
                                f"перевели нужную сумму\nВ сообщении к переводу <b>обязательно</b> укажите код: <b>"
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

                    application.price = price
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
                        except Exception as e:
                            print(e)

                    p = application.com_value
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

                    p = application.com_value
                    to_pay = round((p / 100) * price, 2)

                    application.in_working = False
                    application.price = price
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

    dp.include_router(router)
