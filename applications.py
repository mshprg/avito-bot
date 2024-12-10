import os
import time
import uuid
from time import sleep
import requests
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InputMediaPhoto, BufferedInputFile, InputMediaDocument
from sqlalchemy import select, and_
import avito
import config
import kb
from message_processing import send_state_message, send_state_media
from models.addiction import Addiction
from models.application import Application
from db import AsyncSessionLocal
from models.item_addiction import ItemAddiction
from models.mask import Mask
from models.subscription import Subscription
from models.user import User
from models.work import Work


# Функция для отображения заявки пользователю
# session - сессия базы данных для сохранения данных
# application - объект заявки, содержащий информацию о типе, содержимом и местоположении
# user_city - город пользователя, используемый для фильтрации заявок по локации
# bot - экземпляр бота для отправки сообщений
# chat_id - ID чата, куда будет отправлено сообщение
# is_root_admin - флаг, указывающий, является ли пользователь главным администратором
async def show_application(session, application, user_city, bot: Bot, chat_id, is_root_admin=False):
    try:
        # Получение списка локаций из заявки
        location = application.item_location.split(', ')

        # Если пользователь не является администратором и его город не совпадает с локацией заявки,
        # ничего не отправляется
        if user_city not in location and not is_root_admin:
            return

        # Формирование текста для отправки
        text = "<b>"

        # Если пользователь главный администратор, добавляем информацию о локации в сообщение
        if is_root_admin:
            text += "Локация: "
            for loc in location:
                text += f"{loc} "
            text += "\n\n"

        # Создание клавиатуры для взаимодействия с заявкой
        keyboard = kb.create_application_keyboard()

        # Обработка заявки в зависимости от её типа
        if application.type == 'text':
            # Форматирование текста заявки
            text += f"Заявка от пользователя {application.username}:</b>\n\n{application.content}"

            # Отправка сообщения с текстовой заявкой
            m = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )

            # Сохранение информации о сообщении в базе данных
            addiction = Addiction(
                application_id=application.id,
                telegram_message_id=m.message_id,
                telegram_chat_id=m.chat.id
            )
            session.add(addiction)

        elif application.type == 'image':
            # Загрузка изображения по URL
            response = requests.get(application.content)
            if response.status_code != 200:
                print(f"Не удалось скачать картинку. Код ошибки: {response.status_code}")
                return

            # Чтение содержимого файла
            file_bytes = response.content
            name = str(uuid.uuid4())

            # Форматирование текста для изображения
            text += f"Заявка от пользователя {application.username}:</b>"

            # Создание объекта изображения для отправки
            media = InputMediaPhoto(
                media=BufferedInputFile(file_bytes, filename=f'image_{name}.jpg'),
            )

            # Отправка изображения и получение идентификатора сообщения
            m = (await bot.send_media_group(
                chat_id=chat_id,
                media=[media]
            ))[0]

            # Сохранение информации о сообщении с изображением
            addiction1 = Addiction(
                application_id=application.id,
                telegram_message_id=m.message_id,
                telegram_chat_id=m.chat.id,
            )

            # Отправка текста заявки после изображения
            m = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )

            # Сохранение информации о текстовом сообщении
            addiction2 = Addiction(
                application_id=application.id,
                telegram_message_id=m.message_id,
                telegram_chat_id=m.chat.id,
            )
            session.add(addiction1)
            session.add(addiction2)

        else:
            # Если тип заявки не поддерживается, отправляется уведомление с текстом
            text += (f"Заявка от пользователя {application.username}:</b>\n\nДанный тип сообщения невозможно "
                     f"обработать в Telegram, но вы можете взять заявку")

            # Отправка уведомления
            m = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )

            # Сохранение информации о сообщении
            addiction = Addiction(
                application_id=application.id,
                telegram_message_id=m.message_id,
                telegram_chat_id=m.chat.id,
            )
            session.add(addiction)

        # Небольшая задержка перед следующей отправкой для предотвращения перегрузки
        sleep(0.2)
    except Exception as e:
        print(e)


# Функция для отображения доступных заявок пользователю
# bot - экземпляр бота для отправки сообщений
# user_id - идентификатор пользователя в Telegram
# chat_id - идентификатор чата для отправки заявок
async def show_applications(bot, user_id, chat_id):
    # Открытие асинхронной сессии для взаимодействия с базой данных
    async with AsyncSessionLocal() as session:
        async with session.begin():
            # Проверка, не находится ли пользователь в рабочем состоянии, не заблокирован ли он
            result = await session.execute(
                select(User).filter(and_(
                    User.telegram_user_id == user_id,
                    User.in_working == False,
                    User.banned == False,
                ))
            )
            user = result.scalars().first()

            # Проверка наличия действующей подписки у пользователя
            result = await session.execute(
                select(Subscription).filter(and_(
                    Subscription.telegram_user_id == user_id,
                    Subscription.end_time > int(time.time() * 1000)  # Время окончания подписки в будущем
                ))
            )
            subscription = result.scalars().first()

            # Если пользователь не найден или подписки нет, завершение функции
            if user is None or subscription is None:
                return

            # Получение масок, связанных с пользователем
            result = await session.execute(
                select(Mask).filter(Mask.telegram_user_id == user_id)
            )
            masks = result.scalars().all()

            # Сбор идентификаторов заявок, на которые наложены маски
            application_ids = []
            for mask in masks:
                application_ids.append(mask.application_id)

            # Формирование фильтров для выборки заявок
            filters = [
                Application.in_working == False,  # Заявка не находится в работе
                Application.working_user_id == -1,  # У заявки нет закрепленного пользователя
                Application.item_location != "None",  # У заявки указана локация
            ]

            # Исключение заявок, на которые у пользователя есть маски
            if len(application_ids) != 0:
                filters.append(Application.id.notin_(application_ids))

            # Получение заявок, соответствующих фильтрам
            result = await session.execute(
                select(Application).filter(and_(*filters))
            )
            applications = result.scalars().all()

            # Отображение заявок пользователю
            for application in applications:
                await show_application(
                    session=session,  # Передача сессии для сохранения данных
                    application=application,  # Объект заявки
                    bot=bot,  # Экземпляр бота
                    chat_id=chat_id,  # Идентификатор чата
                    user_city=user.city,  # Город пользователя для фильтрации заявок
                    is_root_admin=user.admin,  # Проверка, является ли пользователь администратором
                )

        # Завершение транзакции и фиксация изменений
        await session.commit()


# Функция для показа сообщений из чата Avito и действий по заявке
# state - текущее состояние FSM
# bot - экземпляр Telegram-бота
# avito_chat_id - идентификатор чата на Avito
# avito_user_id - идентификатор пользователя на Avito
# telegram_chat_id - идентификатор чата в Telegram
# author_id - идентификатор автора сообщения на Avito
# username - имя пользователя автора сообщения
async def show_messages_for_application(state, bot: Bot, avito_chat_id, avito_user_id, telegram_chat_id, author_id, username):
    # Получение списка сообщений из чата Avito
    messages = avito.get_messages(
        chat_id=avito_chat_id,
        user_id=avito_user_id,
    )['messages']

    # Реверс списка сообщений, чтобы начинать с самого раннего
    messages.reverse()

    # Определение текущей директории и путей к файлам шаблонов документов
    current_dir = os.getcwd()
    path_1 = os.path.join(current_dir, "files/dogovor.docx")
    path_2 = os.path.join(current_dir, "files/act.docx")
    path_3 = os.path.join(current_dir, "files/raspiska.docx")

    # Чтение файлов шаблонов документов в байтовом формате
    file1_bytes = open(path_1, "rb").read()
    file2_bytes = open(path_2, "rb").read()
    file3_bytes = open(path_3, "rb").read()

    # Создание медиа-документов для отправки в Telegram
    doc1 = InputMediaDocument(media=BufferedInputFile(file1_bytes, filename="Образец договора возмездного оказания услуг.docx"))
    doc2 = InputMediaDocument(media=BufferedInputFile(file2_bytes, filename="Акт приёмки-сдачи услуг.docx"))
    doc3 = InputMediaDocument(media=BufferedInputFile(file3_bytes, filename="Расписка о получении денежных средств.docx"))

    # Группировка документов в список для отправки
    media = [doc1, doc2, doc3]

    # Отправка документов пользователю
    await send_state_media(
        state=state,
        chat_id=telegram_chat_id,
        media=media,
        bot=bot
    )

    # Текст с инструкциями для действий по заявке
    text = (
        "*Действия с заявкой:*\n_Завершить работу_ \- работа по заявке полностью выполнена, оплата получена\n"
        "_Отказаться от заявки_ \- отказ от работы с заявкой, вы больше не сможете взять эту заявку, "
        "вам будет возвращена половина заплаченной комиссии"
    )

    # Отправка текста с клавиатурой для выбора действий
    keyboard = kb.create_application_actions_keyboard()
    await send_state_message(
        state=state,
        keyboard=keyboard,
        chat_id=telegram_chat_id,
        bot=bot,
        text=text,
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    # Обработка каждого сообщения из чата Avito
    for message in messages:
        sleep(0.3)  # Искусственная задержка для предотвращения ограничения на частоту запросов
        # Определение имени автора сообщения
        name = username if message['author_id'] == int(author_id) else "Вас"

        # Обработка текстового сообщения
        if message['type'] == 'text':
            text = f"<b>Сообщение от {name}:</b>\n\n{message['content']['text']}"
            await send_state_message(
                chat_id=telegram_chat_id,
                bot=bot,
                state=state,
                text=text,
                parse_mode=ParseMode.HTML,
            )

        # Обработка сообщения с изображением
        elif message['type'] == 'image':
            data = message['content']['image']['sizes']['1280x960']
            text = f"<b>Сообщение от {name}:</b>"
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

        # Обработка неподдерживаемых типов сообщений
        else:
            text = f"<b>Сообщение от {name}:</b>\n\nТип сообщения не поддерживается"
            await send_state_message(
                state=state,
                chat_id=telegram_chat_id,
                bot=bot,
                text=text,
                parse_mode=ParseMode.HTML,
            )


# Отправка сообщения в чат авито
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
        sleep(0.1)
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
        except Exception as e:
            print(e)


async def delete_messages_for_application(session, bot: Bot, application_id, skip_user_ids=None):
    if skip_user_ids is None:
        skip_user_ids = []
    result = await session.execute(
        select(Addiction).filter(
            Addiction.application_id == application_id)
    )
    addictions = result.scalars().all()

    for ad in addictions:
        sleep(0.1)
        if ad.telegram_chat_id in skip_user_ids:
            continue
        try:
            await bot.delete_message(
                chat_id=ad.telegram_chat_id,
                message_id=ad.telegram_message_id,
            )
        except Exception as e:
            print(e)
        await session.delete(ad)


async def delete_applications_for_user(session, bot: Bot, telegram_chat_id, skip_ids=None):
    if skip_ids is None:
        skip_ids = []
    result = await session.execute(
        select(Addiction).filter(
            Addiction.telegram_chat_id == telegram_chat_id)
    )
    current_user_addictions = result.scalars().all()

    for ad in current_user_addictions:
        sleep(0.1)
        if ad.application_id in skip_ids:
            continue
        try:
            await bot.delete_message(
                chat_id=ad.telegram_chat_id,
                message_id=ad.telegram_message_id,
            )
        except Exception as e:
            print(e)
        await session.delete(ad)


# Working only in session!!!
async def get_application_by_user(session, user_id):
    result = await session.execute(
        select(Work).filter(and_(
            Work.telegram_user_id == user_id
        ))
    )
    work = result.scalars().first()

    result = await session.execute(
        select(Application).filter(
            Application.id == work.application_id
        )
    )
    application = result.scalars().first()

    return application, work
