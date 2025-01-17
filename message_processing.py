import asyncio
import datetime
import re

from time import sleep

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from models.user import User

from datetime import timezone, timedelta, datetime


async def delete_messages(bot, ids, chat_id):
    try:
        await bot.delete_messages(
            chat_id=chat_id,
            message_ids=ids,
        )
        ids.clear()
    except Exception as e:
        print(e)


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
            m = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=parse_mode,
            )
        else:
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


def to_date(timestamp, only_date=False):
    dt_object = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
    date_utc_plus_3 = dt_object.astimezone(timezone(timedelta(hours=3)))
    if only_date:
        formatted_date = date_utc_plus_3.strftime('%d-%m-%Y')
    else:
        formatted_date = date_utc_plus_3.strftime('%H:%M:%S %d-%m-%Y')
    return formatted_date


def contains_phone_number(message):
    words_to_digits = {
        'not_multi':
            {'ноль': 0, 'один': 1, 'два': 2, 'три': 3, 'четыре': 4,
            'пять': 5, 'шесть': 6, 'семь': 7, 'восемь': 8, 'девять': 9,
            'десять': 10, 'одиннадцать': 11, 'двенадцать': 12, 'тринадцать': 13,
            'четырнадцать': 14, 'пятнадцать': 15, 'шестнадцать': 16,
            'семнадцать': 17, 'восемнадцать': 18, 'девятнадцать': 19},
        'multi': 
            {
                'двадцать': 20, 'тридцать': 30, 'сорок': 40, 'пятьдесят': 50,
                'шестьдесят': 60, 'семьдесят': 70, 'восемьдесят': 80, 'девяносто': 90,
                'сто': 100, 'двести': 200, 'триста': 300, 'четыреста': 400,
                'пятьсот': 500, 'шестьсот': 600, 'семьсот': 700, 'восемьсот': 800,
                'девятьсот': 900
            }
    }

    def replace_words_with_digits(text):
        # Разбиваем текст на слова
        words = text.lower().split()
        result = []
        current_number = 0

        for word in words:
            if word in words_to_digits['not_multi'] or word in words_to_digits['multi']:
                print(word)
                if words_to_digits['multi'].get(word):
                    current_number += words_to_digits['multi'].get(word)
                    
                    print(current_number)
                
                elif words_to_digits['not_multi'].get(word):
                    current_number += words_to_digits['not_multi'].get(word)
                    
                    print(current_number)
                    
                    result.append(str(current_number))
                    current_number = 0
                
            else:
                if current_number > 0:
                    result.append(str(current_number))
                    current_number = 0
                result.append(word)
        
        print(current_number)
        if current_number > 0:
            result.append(str(current_number))

        return ' '.join(result)

    # Преобразуем текст
    message = replace_words_with_digits(message)
    print(message)
    # Регулярное выражение для поиска номеров телефонов
    phone_pattern = re.compile(
        r'\b(?:\+?7|8)?[-.\s()]*(\d{3})[-.\s()]*(\d{3})[-.\s()]*(\d{2})[-.\s()]*(\d{2})\b'
    )

    # Поиск номера телефона
    return bool(phone_pattern.search(message))
