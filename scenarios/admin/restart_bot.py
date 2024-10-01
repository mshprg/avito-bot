from time import sleep

import requests
from aiogram import Router, Bot, F, types
from aiogram.filters import Command
from sqlalchemy import select

import callbacks
import config
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from models.user import User


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(F.text, Command('restart-bot'), UserFilter(check_admin=True))
    async def restart_bot_command_handler(message: types.Message):
        try:
            await message.answer(
                text="Вы уверены что хотите перезагрузить бота?",
                reply_markup=kb.create_restart_bot_keyboard(),
            )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.RESTART_BOT_CALLBACK, UserFilter(check_admin=True))
    async def restart_bot_action(callback_query: types.CallbackQuery):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(User.banned == False)
                    )
                    users = result.scalars().all()

                    for u in users:
                        sleep(0.2)
                        try:
                            await bot.send_message(
                                text="<b>Внимание!</b>\nБот сейчас будет перезагружается.",
                                chat_id=u.telegram_chat_id,
                            )
                        except Exception as e:
                            pass

                    container_name = config.DOCKER_CONTAINER_NAME
                    api_url = config.DOCKER_API_URL
                    response = requests.post(f'{api_url}/containers/{container_name}/restart')

                    if response.status_code == 204:
                        await callback_query.message.reply("Бот успешно перезагружен.")
                    else:
                        await callback_query.message.reply("Ошибка при перезагрузке бота.")
        except Exception as e:
            print(e)

    dp.include_router(router)
