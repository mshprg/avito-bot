from asyncio import sleep
import requests
from aiogram import Router, Bot, F, types
from aiogram.enums import ParseMode
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

    # Слушатлель команды перезапуска
    @router.message(F.text, Command('restart'), UserFilter(check_admin=True))
    async def restart_bot_command_handler(message: types.Message):
        try:
            # Отправляем сообщение с кнопками подтверждения перезагрузки бота
            await message.answer(
                text="Вы уверены что хотите перезагрузить бота?",
                reply_markup=kb.create_restart_bot_keyboard(),  # Клавиатура с кнопками подтверждения
            )
        except Exception as e:
            print(e)

    # Обработчик кнопки подтверждения перезагрузки
    @router.callback_query(F.data == callbacks.RESTART_BOT_CALLBACK, UserFilter(check_admin=True))
    async def restart_bot_action(callback_query: types.CallbackQuery):
        try:
            # Открываем сессию для доступа к базе данных
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Извлекаем всех пользователей, которые не заблокированы
                    result = await session.execute(
                        select(User).filter(User.banned == False)
                    )
                    users = result.scalars().all()

                    # Уведомляем каждого пользователя о перезагрузке бота
                    for u in users:
                        await sleep(0.2)  # Небольшая задержка между отправкой сообщений, чтобы телега не ругалась
                        try:
                            await bot.send_message(
                                text="<b>Внимание!</b>\nБот перезагружается, дождитесь сообщения о перезапуске.",
                                chat_id=u.telegram_chat_id,
                                parse_mode=ParseMode.HTML,  # Форматирование сообщения как HTML
                            )
                        except Exception as e:
                            print(e)

            # Отправляем запрос к Docker API для перезагрузки контейнера бота
            container_name = config.DOCKER_CONTAINER_NAME  # Имя контейнера из конфигурации
            api_url = config.DOCKER_API_URL  # URL API Docker
            response = requests.post(f'{api_url}/containers/{container_name}/restart')  # Выполняем перезагрузку

            # Проверяем статус ответа от Docker API
            if response.status_code == 204:
                # Уведомляем администратора об успешной перезагрузке
                await callback_query.message.reply("Бот успешно перезагружен.")
            else:
                # Уведомляем администратора об ошибке
                await callback_query.message.reply("Ошибка при перезагрузке бота.")
        except Exception as e:
            print(e)

    dp.include_router(router)
