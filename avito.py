import asyncio
import uuid
import aiohttp
from aiogram.types import InputMediaPhoto, BufferedInputFile
from sqlalchemy import select

import config
import main
import requests
from time import time
from aiohttp import web
from db import AsyncSessionLocal
from message_processing import add_message_ids
from models.application import Application
from models.item import Item
from models.user import User

handled_message = []
token_info = None


def get_token_info():
    global token_info
    if token_info is None or token_info['expires_in'] >= time():
        token_url = "https://api.avito.ru/token"

        params = {
            "client_id": config.AVITO_CLIENT_ID,
            "client_secret": config.AVITO_CLIENT_SECRET,
            "grant_type": "client_credentials"
        }
        response = requests.post(token_url, data=params)
        if response.status_code == 200:
            token_info = response.json()
            token_info['expires_in'] += time()

    return token_info


def get_chats(user_id):
    get_token_info()
    get_chats_url = f'https://api.avito.ru/messenger/v2/accounts/{user_id}/chats'

    headers = {
        "Authorization": f"Bearer {token_info['access_token']}"
    }

    params = {
        "chat_type": 'u2i'
    }

    response = requests.get(get_chats_url, headers=headers, params=params)

    if response.status_code != 200:
        print(f"Failed to retrieve data: {response.status_code}")
        return

    chats_data = response.json()

    return chats_data


def get_messages(user_id, chat_id):
    get_token_info()
    get_messages_url = f'https://api.avito.ru/messenger/v3/accounts/{user_id}/chats/{chat_id}/messages'

    headers = {
        "Authorization": f"Bearer {token_info['access_token']}"
    }

    response = requests.get(get_messages_url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to retrieve data: {response.status_code}")
        return

    messages_data = response.json()

    return messages_data


def get_chat(user_id, chat_id):
    get_token_info()
    get_chat_url = f'https://api.avito.ru/messenger/v2/accounts/{user_id}/chats/{chat_id}'

    headers = {
        "Authorization": f"Bearer {token_info['access_token']}"
    }

    response = requests.get(get_chat_url, headers=headers)

    if response.status_code != 200:
        print(f"Failed to retrieve data: {response.status_code}")
        return

    chat_data = response.json()

    return chat_data


async def send_message(user_id, chat_id, text):
    get_token_info()
    send_message_url = f'https://api.avito.ru/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages'

    headers = {
        "Authorization": f"Bearer {token_info['access_token']}",
        'Content-Type': 'application/json',
    }

    body = {
        "message": {
            "text": text
        },
        "type": "text"
    }

    response = requests.post(send_message_url, headers=headers, json=body)

    if response.status_code != 200:
        print(f"Failed to retrieve data: {response.status_code}")
        return

    send_data = await response.json()

    return send_data


def get_username(chat_info, user_id):
    users = chat_info['users']
    for u in users:
        if u['id'] != user_id:
            return u['name']

    return None


async def handle_webhook_message(request):
    get_token_info()
    data = await request.json()

    value = data.get('payload')['value']

    m_id = value['id']
    chat_id = value['chat_id']
    user_id = value['user_id']
    author_id = value['author_id']
    created = value['created']
    m_type = value['type']
    if m_type == 'text':
        content = value['content']['text']
    elif m_type == 'image':
        content = value['content']['image']['sizes']['1280x960']
    else:
        content = "Unsupported type of file"

    if chat_id is None or chat_id == '0':
        return

    messages = get_messages(user_id, chat_id)['messages']

    d = {'is_f': True}
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(Application).filter(Application.avito_chat_id == chat_id)
            )
            application_db = result.scalars().first()

            if application_db is not None:
                d['is_f'] = False

    if d['is_f']:
        if len(messages) <= 2:
            await add_new_application(
                user_id=user_id,
                chat_id=chat_id,
                m_id=m_id,
                m_type=m_type,
                content=content,
                author_id=author_id,
                created=created
            )
    else:
        await send_user_message(
            user_id=user_id,
            chat_id=chat_id,
            m_type=m_type,
            content=content,
            author_id=author_id,
            created=created
        )

    print(data.get('payload'))

    return web.json_response({"ok": True})


async def send_user_message(user_id, chat_id, m_type, content, author_id, created):
    if int(user_id) != int(author_id):
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    select(Application).filter(Application.avito_chat_id == chat_id)
                )
                application_db = result.scalars().first()

                application_db.last_message_time = int(created)
                application_db.last_message_text = content

                telegram_user_id = application_db.working_user_id

                result = await session.execute(
                    select(User).filter(User.telegram_user_id == telegram_user_id)
                )
                user = result.scalars().first()

                if user is not None and user.in_working:
                    if m_type == 'text':
                        m = await main.bot.send_message(
                            chat_id=user.telegram_chat_id,
                            text=content,
                        )
                    elif m_type == 'image':
                        response = requests.get(content)
                        if response.status_code != 200:
                            return
                        file_bytes = response.content
                        name = str(uuid.uuid4())
                        media = InputMediaPhoto(
                            media=BufferedInputFile(file_bytes, filename=f'image_{name}.jpg'),
                        )
                        m = (await main.bot.send_media_group(chat_id=user.telegram_chat_id, media=[media]))[0]
                    else:
                        m = await main.bot.send_message(chat_id=user.telegram_chat_id,
                                                        text="Неподдерживаемый тип данных")
                    await add_message_ids(
                        session=session,
                        telegram_chat_id=user.telegram_chat_id,
                        data=m.message_id,
                    )

            await session.commit()


async def add_new_application(user_id, chat_id, m_id, m_type, content, author_id, created):

    chat = get_chat(user_id, chat_id)
    username = get_username(chat, user_id)
    from applications import show_application, show_new_item_for_admin

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(Application).filter(Application.avito_chat_id == chat_id)
            )
            application_db = result.scalars().first()

            if application_db is None and author_id != user_id:

                result = await session.execute(
                    select(Item).filter(Item.avito_item_id == int(chat['context']['value']['id']))
                )
                item = result.scalars().first()

                item_location = "None"
                if item is not None:
                    item_location = item.location
                else:
                    item = Item(
                        avito_item_id=int(chat['context']['value']['id']),
                        url=chat['context']['value']['url'],
                        location="None"
                    )
                    session.add(item)

                application = Application(
                    avito_chat_id=chat_id,
                    avito_message_id=m_id,
                    in_working=False,
                    working_user_id=-1,
                    item_name=chat['context']['value']['title'],
                    item_location=item_location,
                    item_id=int(chat['context']['value']['id']),
                    type=m_type,
                    content=content,
                    author_id=str(author_id),
                    user_id=str(user_id),
                    created=int(created),
                    last_message_time=int(created),
                    last_message_text=content,
                    username=username,
                    pay_type="None"
                )

                session.add(application)
                await session.flush()

                if item_location == "None":
                    await show_new_item_for_admin(
                        session=session,
                        bot=main.bot,
                        url=chat['context']['value']['url'],
                        avito_item_id=item.avito_item_id,
                        item_id=item.id
                    )
                else:
                    result = await session.execute(
                        select(User).filter(
                            User.in_working == False
                        )
                    )
                    users = result.scalars().all()

                    for user in users:
                        await show_application(
                            session=session,
                            application=application,
                            user_city=user.city,
                            is_admin=user.admin,
                            bot=main.bot,
                            chat_id=user.telegram_chat_id
                        )

        await session.commit()
        print("New application has been added")


async def register_webhook():
    url = "https://api.avito.ru/messenger/v3/webhook"
    get_token_info()
    access_token = token_info['access_token']
    webhook_url = f"{config.WEBHOOK_HOST}{config.WEBHOOK_PATH}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "url": webhook_url
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                print("Webhook registered successfully")
            else:
                response_text = await response.text()
                print("Failed to register webhook", response_text)


async def start_avito_webhook(function):
    await register_webhook()
    app = web.Application()
    app.router.add_post(config.WEBHOOK_PATH, function)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, port=3001)
    await site.start()
    print("Server running on port 3001")
    while True:
        await asyncio.sleep(1500)
