from aiogram import Router, Bot, types, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id
from models.feedback import Feedback
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    # Обработчик сообщений с текстом "Обратная связь" от пользователей, прошедших фильтр UserFilter
    @router.message(F.text == "Обратная связь", UserFilter())
    async def send_feedback_callback(message: types.Message, state: FSMContext):
        try:
            # Добавляет ID сообщения в состояние для последующего управления (удаление/обновление сообщений)
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="feedback_ids"
            )
            # Отправляет сообщение с кнопками действий для обратной связи
            await send_state_message(
                state=state,
                message=message,
                text="*Действия:*",
                parse_mode=ParseMode.MARKDOWN_V2,
                keyboard=kb.create_feedback_actions_keyboard(),  # Генерация клавиатуры с действиями
                state_name="feedback_ids"
            )
        except Exception as e:
            print(e)

    # Функция отправки сообщения с текстом обратной связи
    async def send_feedback_message(text, type_feedback, callback_query: types.CallbackQuery, state: FSMContext):
        try:
            # Отправляет сообщение с инструкциями для ввода обратной связи
            await send_state_message(
                state=state,
                message=callback_query.message,
                text=text,
                state_name="feedback_ids",
            )
            # Обновляет данные состояния, чтобы сохранить тип обратной связи
            await state.update_data(feedback=type_feedback)
            # Устанавливает новое состояние для ожидания ввода текста
            await state.set_state(States.feedback)
        except Exception as e:
            print(e)

    # Обработчик callback-запроса для отправки вопроса
    @router.callback_query(F.data == callbacks.SEND_QUESTION_CALLBACK, UserFilter())
    async def send_question_callback(callback_query: types.CallbackQuery, state: FSMContext):
        # Вызывает функцию отправки сообщения для обработки вопросов
        await send_feedback_message(
            text="Отправьте вопрос",  # Текст инструкции
            type_feedback="question",  # Тип обратной связи
            callback_query=callback_query,
            state=state
        )

    # Обработчик callback-запроса для отправки предложений по улучшению
    @router.callback_query(F.data == callbacks.SEND_IMPROVEMENT_CALLBACK, UserFilter())
    async def send_improvement_callback(callback_query: types.CallbackQuery, state: FSMContext):
        # Вызывает функцию отправки сообщения для обработки предложений
        await send_feedback_message(
            text="Предложите улучшение",  # Текст инструкции
            type_feedback="improvement",  # Тип обратной связи
            callback_query=callback_query,
            state=state
        )

    # Обработчик сообщений от пользователей, находящихся в состоянии ожидания ввода текста обратной связи
    @router.message(States.feedback)
    async def read_feedback(message: types.Message, state: FSMContext):
        try:
            # Сохраняет ID сообщения в состоянии для управления им позже
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="feedback_ids"
            )

            # Сохраняет текст обратной связи в базу данных
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Получение данных из состояния
                    user_data = await state.get_data()
                    type_feedback = user_data.get("feedback", "None")  # Тип обратной связи
                    feedback = Feedback(
                        type=type_feedback,  # Тип обратной связи
                        text=message.text,  # Текст обратной связи
                        telegram_user_id=message.from_user.id  # ID пользователя Telegram
                    )
                    # Добавляет обратную связь в сессию для сохранения в базе данных
                    session.add(feedback)
                # Сохраняет изменения в базе данных
                await session.commit()

            # Отправляет подтверждающее сообщение об успешной отправке
            await send_state_message(
                state=state,
                message=message,
                text="Запрос отправлен",
                keyboard=kb.create_clear_feedback_keyboard(),  # Клавиатура с кнопкой для очистки
                state_name="feedback_ids",
            )
        except Exception as e:
            # В случае ошибки предлагает ввести текст заново
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, введите текст заново",
                state_name="feedback_ids",
            )
            # Устанавливает состояние для повторного ожидания текста
            await state.set_state(States.feedback)
            print(e)

    dp.include_router(router)
