from aiogram import Router, Bot, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_

import kb
from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import add_state_id, send_state_message
from models.feedback import Feedback
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    # Обработчик команды /myimprovements
    @router.message(Command('myimprovements'), StateFilter(None, States.message), UserFilter())
    async def get_my_improvements(message: types.Message, state: FSMContext):
        try:
            # Добавляем сообщение в стейт массив id - feedback_ids
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="feedback_ids",
            )

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Получаем все проедлежения по улучшению для данного юзера
                    result = await session.execute(
                        select(Feedback).filter(and_(
                            Feedback.telegram_user_id == message.from_user.id,
                            Feedback.type == "improvement"
                        ))
                    )
                    feedbacks = result.scalars().all()

                    # Если предложений не поступало
                    if len(feedbacks) == 0:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Вы не пердлагали улучшений",
                            keyboard=kb.create_clear_feedback_keyboard(),
                            state_name="feedback_ids",
                        )
                        return

                    # Отправляем данные по каждому предложению
                    for feedback in feedbacks:
                        await send_feedback(state, message, feedback, 0)

                    # Отправляем сообщение с клавиатурой
                    await send_state_message(
                        state=state,
                        message=message,
                        text="Действия",
                        keyboard=kb.create_clear_feedback_keyboard(),
                        state_name="feedback_ids",
                    )
        except Exception as e:
            print(e)

    # Обработчик команды /myquestions
    @router.message(Command('myquestions'), StateFilter(None, States.message), UserFilter())
    async def get_my_questions(message: types.Message, state: FSMContext):
        try:
            # Добавляем сообщение в стейт массив id - feedback_ids
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="feedback_ids",
            )

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Получаем все вопросы для данного юзера
                    result = await session.execute(
                        select(Feedback).filter(and_(
                            Feedback.telegram_user_id == message.from_user.id,
                            Feedback.type == "question"
                        ))
                    )
                    feedbacks = result.scalars().all()

                    # Если вопросов не поступало
                    if len(feedbacks) == 0:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Вы не задавали вопросов",
                            keyboard=kb.create_clear_feedback_keyboard(),
                            state_name="feedback_ids",
                        )
                        return

                    # Отправляем данные по каждому вопросу
                    for feedback in feedbacks:
                        await send_feedback(state, message, feedback, 1)

                    # Отправляем сообщение с клавиатурой
                    await send_state_message(
                        state=state,
                        message=message,
                        text="Действия",
                        keyboard=kb.create_clear_feedback_keyboard(),
                        state_name="feedback_ids",
                    )
        except Exception as e:
            print(e)

    dp.include_router(router)


async def send_feedback(state, message, feedback, type_feedback: int):
    answer = "Пока нет ответа" if len(feedback.answer) == 0 else feedback.answer
    text = (f"<b>Ваш {'вопрос' if type_feedback == 0 else 'предложение'}</b>:"
            f"\n{feedback.text}\n\n<b>Ответ от администратора:</b>\n{answer}")
    await send_state_message(
        state=state,
        message=message,
        text=text,
        parse_mode=ParseMode.HTML,
        state_name="feedback_ids",
    )