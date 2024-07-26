import os
import uuid
from time import sleep
import requests
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InputMediaPhoto, BufferedInputFile, InputMediaDocument
from sqlalchemy import select, and_
import avito
import kb
from message_processing import send_state_message, send_state_media
from models.addiction import Addiction
from models.application import Application
from db import AsyncSessionLocal
from models.confirmation_addiction import ConfirmationAddiction
from models.item_addiction import ItemAddiction
from models.mask import Mask
from models.user import User


async def show_application(session, is_admin, application, user_city, bot: Bot, chat_id):
    location = application.item_location.split(', ')
    if user_city not in location:
        return
    if is_admin:
        keyboard = kb.create_application_admin_keyboard()
    else:
        keyboard = kb.create_application_keyboard()
    if application.type == 'text':
        text = f"<b>Заявка от пользователя {application.username}:</b>\n\n{application.content}"
        m = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
        addiction = Addiction(
            application_id=application.id,
            telegram_message_id=m.message_id,
            telegram_chat_id=m.chat.id
        )
        session.add(addiction)
    elif application.type == 'image':
        response = requests.get(application.content)
        if response.status_code != 200:
            print(f"Не удалось скачать картинку. Код ошибки: {response.status_code}")
            return
        file_bytes = response.content
        name = str(uuid.uuid4())
        text = f"<b>Заявка от пользователя {application.username}:</b>"
        media = InputMediaPhoto(
            media=BufferedInputFile(file_bytes, filename=f'image_{name}.jpg'),
        )
        m = (await bot.send_media_group(
            chat_id=chat_id,
            media=[media]
        ))[0]
        addiction1 = Addiction(
            application_id=application.id,
            telegram_message_id=m.message_id,
            telegram_chat_id=m.chat.id,
        )
        m = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
        addiction2 = Addiction(
            application_id=application.id,
            telegram_message_id=m.message_id,
            telegram_chat_id=m.chat.id,
        )
        session.add(addiction1)
        session.add(addiction2)
    else:
        text = ("Вам прислал сообщение новый пользователь, к сожалению данный тип сообщения "
                "невозможно обработать в Telegram, но вы можете взять заявку")
        m = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
        )
        addiction = Addiction(
            application_id=application.id,
            telegram_message_id=m.message_id,
            telegram_chat_id=m.chat.id,
        )
        session.add(addiction)


async def show_applications(bot, user_id, chat_id):
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(User).filter(User.telegram_user_id == user_id)
            )
            user = result.scalars().first()

            result = await session.execute(
                select(Mask).filter(Mask.telegram_user_id == user_id)
            )
            masks = result.scalars().all()

            application_ids = []

            for mask in masks:
                application_ids.append(mask.application_id)

            filters = [
                Application.in_working == False,
                Application.working_user_id == -1,
                Application.item_location != "None",
            ]

            if len(application_ids) != 0:
                filters.append(Application.id.notin_(application_ids))

            result = await session.execute(
                select(Application).filter(and_(*filters))
            )
            applications = result.scalars().all()
            for application in applications:
                await show_application(
                    session=session,
                    is_admin=user.admin,
                    application=application,
                    bot=bot,
                    chat_id=chat_id,
                    user_city=user.city
                )

        await session.commit()


async def show_messages_for_application(state, bot: Bot, avito_chat_id, avito_user_id, telegram_chat_id, author_id, username):

    messages = avito.get_messages(
        chat_id=avito_chat_id,
        user_id=avito_user_id,
    )['messages']

    messages.reverse()

    current_dir = os.getcwd()

    path_1 = os.path.join(current_dir, "files/dogovor.docx")
    path_2 = os.path.join(current_dir, "files/act.docx")
    path_3 = os.path.join(current_dir, "files/raspiska.docx")

    file1_bytes = open(path_1, "rb").read()
    file2_bytes = open(path_2, "rb").read()
    file3_bytes = open(path_3, "rb").read()

    doc1 = InputMediaDocument(media=BufferedInputFile(file1_bytes, filename="Образец договора возмездного оказания "
                                                                            "услуг.docx"))
    doc2 = InputMediaDocument(media=BufferedInputFile(file2_bytes, filename="Акт приёмки-сдачи услуг.docx"))
    doc3 = InputMediaDocument(media=BufferedInputFile(file3_bytes, filename="Расписка о получении денежных средств.docx"))

    media = [doc1, doc2, doc3]

    keyboard = kb.create_application_actions_keyboard()

    await send_state_media(
        state=state,
        chat_id=telegram_chat_id,
        media=media,
        bot=bot
    )

    text = (
        "*Дествия с зявкой:*\n_Завершить работу_ \- работа по зявке полностью выполнена, оплата получена\n_Отказаться "
        "от заявки_ \- отказ от работы с заявкой, вы больше не сможете взять эту заявку")

    await send_state_message(
        state=state,
        keyboard=keyboard,
        chat_id=telegram_chat_id,
        bot=bot,
        text=text,
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    for message in messages:
        sleep(0.2)
        if message['author_id'] == int(author_id):
            name = username
        else:
            name = "Вас"
        if message['type'] == 'text':
            text = f"<b>Сообщение от {name}:</b>\n\n{message['content']['text']}"
            await send_state_message(
                chat_id=telegram_chat_id,
                bot=bot,
                state=state,
                text=text,
                parse_mode=ParseMode.HTML,
            )
        elif message['type'] == 'image':
            data = message['content']['image']['sizes']['1280x960']
            text = f'<b>Сообщение от {name}:</b>'
            response = requests.get(data)
            if response.status_code != 200:
                print(f"Не удалось скачать картинку. Код ошибки: {response.status_code}")
                return
            file_bytes = response.content
            name = str(uuid.uuid4())
            media = InputMediaPhoto(
                media=BufferedInputFile(file_bytes, filename=f'image_{name}.jpg'),
            )
            await send_state_message(
                chat_id=telegram_chat_id,
                bot=bot,
                state=state,
                text=text,
                parse_mode=ParseMode.HTML,
            )
            await send_state_media(
                chat_id=telegram_chat_id,
                bot=bot,
                state=state,
                media=[media]
            )
        else:
            text = f"<b>Сообщение от {name}:</b>\n\nТип сообщения не поддерживается"
            await send_state_message(
                state=state,
                chat_id=telegram_chat_id,
                bot=bot,
                text=text,
                parse_mode=ParseMode.HTML,
            )


async def send_message_for_application(avito_user_id, avito_chat_id, text):
    await avito.send_message(
        user_id=avito_user_id,
        chat_id=avito_chat_id,
        text=text,
    )


async def show_new_item_for_admin(session, bot: Bot, url, item_id, avito_item_id, chat_id=None):

    filters = [
        User.admin == True,
    ]

    if chat_id:
        filters.append(User.telegram_chat_id == chat_id)

    result = await session.execute(
        select(User).filter(and_(*filters))
    )
    users = result.scalars().all()

    text = f"<b>У вас новое объявление:</b>\n\nID: {avito_item_id}\nURL: {url}\n\n Добавьте локацию к этому объявлению"

    for user in users:
        try:
            m = await bot.send_message(
                chat_id=user.telegram_chat_id,
                text=text,
                reply_markup=kb.create_add_city_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            new_item_addiction = ItemAddiction(
                item_id=item_id,
                telegram_message_id=m.message_id,
                telegram_chat_id=user.telegram_chat_id,
            )
            session.add(new_item_addiction)
        except:
            ...


async def show_confirmation_for_admins(session, confirmation, author_user, bot: Bot):
    result = await session.execute(
        select(User).filter(User.admin == True)
    )
    users = result.scalars().all()

    for user in users:
        try:
            text = (f"Перевод от {author_user.name}\nНомер телефона: <b>{author_user.phone}</b>\nКод пользователя: "
                    f"<b>{confirmation.telegram_user_id}</b>\nСумма: <b>{confirmation.amount}</b>")
            m = await bot.send_message(
                chat_id=user.telegram_chat_id,
                text=text,
                reply_markup=kb.create_new_confirmation_actions(),
                parse_mode=ParseMode.HTML
            )
            new_conf_addiction = ConfirmationAddiction(
                confirmation_id=confirmation.id,
                telegram_message_id=m.message_id,
                telegram_chat_id=user.telegram_chat_id,
            )
            session.add(new_conf_addiction)
        except:
            ...
