from aiogram import Router, types, Bot
from aiogram.fsm.context import FSMContext
from applications import send_message_for_application, get_application_by_user
from db import AsyncSessionLocal
from filters import UserFilter
from states import States
from message_processing import add_state_id


def load_handlers(dp, bot: Bot):
    router = Router()

    # Обработчик сообщений для состояния States.message, прошедших фильтр UserFilter
    @router.message(States.message, UserFilter())
    async def send_message(message: types.Message, state: FSMContext):
        try:
            # Проверка на наличие мультимедиа (группы медиа, фото или видео)
            if message.media_group_id or message.photo or message.video:
                # Удаляет мультимедиа-сообщение, так как оно не поддерживается
                await bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                )
                # Сохраняет текущее состояние, чтобы ожидать текстовое сообщение
                await state.set_state(States.message)
                return  # Завершает выполнение обработчика

            # Сохраняет текст сообщения
            text = message.text

            # Добавляет ID сообщения в состояние для последующего управления
            await add_state_id(state, message.message_id)

            # Получает данные из текущего состояния FSM
            data = await state.get_data()
            avito_info = data.get("avito_info", None)  # Пытается получить информацию о чате Avito

            # Если информация о чате Avito отсутствует, загружает ее из базы данных
            if avito_info is None:
                async with AsyncSessionLocal() as session:
                    async with session.begin():
                        # Получает данные о заявке
                        application, _ = await get_application_by_user(session, message.from_user.id)

                        # Сохраняет идентификаторы чата и пользователя Avito
                        avito_chat_id = str(application.avito_chat_id)
                        avito_user_id = str(application.user_id)

                        # Обновляет состояние FSM с полученной информацией
                        await state.update_data(avito_info={
                            'chat_id': avito_chat_id,
                            'user_id': avito_user_id,
                        })
            else:
                # Если информация уже была сохранена, извлекает ее из состояния
                avito_chat_id = avito_info['chat_id']
                avito_user_id = avito_info['user_id']

            # Отправляет сообщение в приложение (например, Avito) через соответствующую функцию
            await send_message_for_application(
                avito_user_id=avito_user_id,  # Идентификатор пользователя Avito
                avito_chat_id=avito_chat_id,  # Идентификатор чата Avito
                text=text,  # Текст сообщения
            )
        except Exception as e:
            # Логирует ошибку и повторно устанавливает текущее состояние для ожидания следующего сообщения
            print(e)
            await state.set_state(States.message)

    dp.include_router(router)
