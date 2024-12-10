from aiogram import Bot, Router, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import callbacks
import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import send_state_message, add_state_id
from models.feedback import Feedback
from models.user import User
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    # Функция для управления вопросами и предложениями по улучшению
    # Извлекает и обрабатывает вопросы или предложения, на которые еще не был дан ответ,
    # отображает их администратору для просмотра и ответа, а также обновляет состояние.
    async def manage_questions_improvements(message: types.Message, state: FSMContext, non_feedback_text, action_text,
                                            type_feedback):
        # Добавляем ID сообщения в состояние для отслеживания взаимодействий администратора
        await add_state_id(
            state=state,
            message_id=message.message_id,
            state_name="feedback_admin_ids"
        )

        # Открываем сессию с базой данных для запроса записей обратной связи
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # Запрашиваем записи обратной связи с заданным типом и пустым ответом
                result = await session.execute(
                    select(Feedback).filter(and_(
                        Feedback.type == type_feedback,
                        Feedback.answer == ""
                    ))
                )
                feedbacks = result.scalars().all()

                # Если не найдено обратной связи, отправляем сообщение администратору
                if len(feedbacks) == 0:
                    await send_state_message(
                        state=state,
                        message=message,
                        text=non_feedback_text,
                        state_name="feedback_admin_ids",
                        keyboard=kb.create_delete_admin_messages_keyboard()
                    )
                    return

                # Формируем список сообщений с обратной связью для отправки админу
                messages = []
                for feedback in feedbacks:
                    # Извлекаем пользователя, который оставил обратную связь
                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == feedback.telegram_user_id
                        )
                    )
                    user = result.scalars().first()

                    # Если пользователь найден, выводим его имя, иначе - "неизвестный пользователь"
                    if user:
                        name = user.name
                    else:
                        name = "неизвестный пользователь"

                    # Формируем текст сообщения с обратной связью и именем пользователя
                    text = f"<b>{action_text} {name}</b>\n\n{feedback.text}"

                    # Отправляем сообщение с кнопками для действий
                    m = await send_state_message(
                        state=state,
                        message=message,
                        text=text,
                        keyboard=kb.create_answer_feedback_keyboard(),
                        parse_mode=ParseMode.HTML,
                        state_name="feedback_admin_ids",
                    )

                    # Сохраняем детали сообщения для дальнейшей обработки
                    messages.append({
                        'message_id': m.message_id,
                        'feedback': feedback.to_dict()
                    })

                # Сохраняем данные о обратной связи в состояние для использования в будущем
                state_feedback = {
                    'messages': messages,
                    'current_feedback': None,
                }
                await state.update_data(visible_feedbacks=state_feedback)

            # Отправляем финальное сообщение администратору, информируя его о возможности действий
            await send_state_message(
                state=state,
                message=message,
                text="Действия",
                keyboard=kb.create_delete_admin_messages_keyboard(),
                state_name="feedback_admin_ids",
            )

    # Обработчик команды для получения неотвеченных вопросов
    @router.message(Command('questions'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def get_feedback(message: types.Message, state: FSMContext):
        try:
            # Вызываем функцию для управления вопросами с типом обратной связи "question"
            await manage_questions_improvements(
                message=message,
                state=state,
                non_feedback_text="Нет неотвеченных вопросов",
                action_text="Спрашивает",
                type_feedback="question"
            )
        except Exception as e:
            print(e)

    # Обработчик команды для получения предложений по улучшению
    @router.message(Command('improvements'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def get_improvements(message: types.Message, state: FSMContext):
        try:
            # Вызываем функцию для управления предложениями с типом обратной связи "improvement"
            await manage_questions_improvements(
                message=message,
                state=state,
                non_feedback_text="Нет предложений по улучшению",
                action_text="Предлагает",
                type_feedback="improvement"
            )
        except Exception as e:
            print(e)

    # Обработчик callback-запроса для ответа на вопрос
    @router.callback_query(F.data == callbacks.ANSWER_QUESTION_CALLBACK, UserFilter(check_admin=True))
    async def answer_question_callback(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            # Извлекаем текущее состояние обратной связи из сессии
            data = await state.get_data()
            state_feedback: dict = data.get("visible_feedbacks", {})
            messages = state_feedback.get("messages", [])

            # Находим соответствующую обратную связь по ID сообщения
            feedback = None
            for m in messages:
                if m['message_id'] == callback_query.message.message_id:
                    feedback = m['feedback']

            # Если обратная связь не найдена, завершаем обработку
            if feedback is None:
                print("Error")
                return

            # Устанавливаем текущую обратную связь для дальнейшей обработки
            state_feedback['current_feedback'] = feedback

            # Просим администратора ввести свой ответ
            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Введите ответ",
                state_name="feedback_admin_ids",
            )

            # Обновляем состояние с текущей обратной связью
            await state.update_data(visible_feedbacks=state_feedback)

            # Устанавливаем состояние для ввода ответа администратора
            await state.set_state(States.visible_feedbacks)

        except Exception as e:
            print(e)

    # Обработчик сообщения, когда администратор отправляет свой ответ на вопрос
    @router.message(States.visible_feedbacks, UserFilter(check_admin=True))
    async def read_answer(message: types.Message, state: FSMContext):
        try:
            # Добавляем ID сообщения в состояние для отслеживания
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="feedback_admin_ids"
            )

            # Извлекаем текущее состояние обратной связи
            data = await state.get_data()
            state_feedback: dict = data.get("visible_feedbacks", {})
            feedback = state_feedback.get("current_feedback", None)

            # Если обратная связь не найдена, завершаем обработку
            if feedback is None:
                print("Error")
                return

            # Открываем сессию для обновления обратной связи с ответом администратора
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Извлекаем запись обратной связи из базы данных
                    result = await session.execute(
                        select(Feedback).filter(
                            Feedback.id == feedback['id']
                        )
                    )
                    feedback = result.scalars().first()

                    # Обновляем ответ на обратную связь
                    feedback.answer = message.text

                # Подтверждаем изменения в базе данных
                await session.commit()

            # Сообщаем админу, что ответ сохранен
            await send_state_message(
                state=state,
                message=message,
                text="Ответ сохранён",
                keyboard=kb.create_delete_admin_messages_keyboard(),
                state_name="feedback_admin_ids",
            )

            # Сбрасываем текущую обратную связь для готовности к следующей обработке
            state_feedback['current_feedback'] = None
            await state.update_data(visible_feedbacks=state_feedback)

        except Exception as e:
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, введите текст заново",
                state_name="feedback_admin_ids",
            )
            await state.set_state(States.visible_feedbacks)
            print(e)

    dp.include_router(router)
