import asyncio
import datetime
from time import sleep

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from models.user import User


async def delete_messages(bot, ids, chat_id):
    try:
        await bot.delete_messages(
            chat_id=chat_id,
            message_ids=ids,
        )
        ids.clear()
    except Exception as e:
        print(e)


async def delayed_execution(func, *args, **kwargs):
    await asyncio.sleep(3)
    await func(*args, **kwargs)


async def try_send_message(func, count=5, **kwargs):
    res = None
    try:
        res = await func(**kwargs)
    except Exception as e:
        count -= 1
        print(e)
        sleep(4)
        if count > 0:
            res = await try_send_message(func=func, count=count, **kwargs)
    return res


def split_list(arr, chunk_size):
    return [arr[i:i + chunk_size] for i in range(0, len(arr), chunk_size)]


async def delete_state_messages(state, bot, chat_id, state_name: str = "ids"):
    data = await state.get_data()
    ids = data.get(state_name)
    chunks = split_list(ids, 50)
    for chunk in chunks:
        sleep(0.5)
        await delete_messages(bot, chunk, chat_id)
    await state.update_data(**{state_name: []})


async def send_state_message(state, message=None, text=None, keyboard=None, chat_id=None, bot: Bot = None,
                             parse_mode=None, state_name: str = "ids") -> Message | None:
    try:
        if chat_id is not None and bot is not None:
            # m = await try_send_message(
            #     func=bot.send_message,
            #     chat_id=chat_id,
            #     text=text,
            #     reply_markup=keyboard,
            #     parse_mode=parse_mode,
            # )
            m = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=parse_mode,
            )
        else:
            # m = await try_send_message(
            #     func=message.answer,
            #     text=text, reply_markup=keyboard, parse_mode=parse_mode
            # )
            m = await message.answer(text=text, reply_markup=keyboard, parse_mode=parse_mode)
        data = await state.get_data()
        ids = data.get(state_name, [])
        ids.append(m.message_id)
        await state.update_data(**{state_name: ids})
        return m
    except Exception as e:
        print(e)


async def reset_state(state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)


async def send_state_media(state, chat_id, bot: Bot, media, state_name: str = "ids") -> list[Message] | None:
    try:
        m = await bot.send_media_group(
            chat_id=chat_id,
            media=media
        )
        data = await state.get_data()
        ids = data.get(state_name, [])
        for message in m:
            ids.append(message.message_id)
        await state.update_data(**{state_name: ids})
        return m
    except Exception as e:
        print(e)


async def add_state_id(state, message_id, state_name: str = "ids"):
    data = await state.get_data()
    ids = data.get(state_name, [])
    ids.append(message_id)
    await state.update_data(**{state_name: ids})


async def add_message_ids(session, telegram_chat_id, data):
    try:
        result = await session.execute(
            select(User).filter(
                User.telegram_chat_id == int(telegram_chat_id))
        )
        user = result.scalars().first()

        if user is None:
            return

        ids = eval(user.income_message_ids)

        if isinstance(data, list):
            for m_id in data:
                ids.append(m_id)
        else:
            ids.append(int(data))

        user.income_message_ids = str(ids)
    except Exception as e:
        print(e)


async def delete_message_ids(session, bot, telegram_chat_id):
    try:
        result = await session.execute(
            select(User).filter(
                User.telegram_chat_id == int(telegram_chat_id))
        )
        user = result.scalars().first()

        if user is None:
            return

        ids = eval(user.income_message_ids)
        chunks = split_list(ids, 50)

        if isinstance(ids, list) and len(ids) != 0:
            for chunk in chunks:
                sleep(0.5)
                await delete_messages(
                    bot=bot,
                    ids=chunk,
                    chat_id=telegram_chat_id
                )

        user.income_message_ids = "[]"
    except Exception as e:
        print(e)


def to_date(timestamp):
    dt_object = datetime.datetime.fromtimestamp(timestamp)
    formatted_date = dt_object.strftime('%H:%M:%S %d-%m-%Y')
    return formatted_date
