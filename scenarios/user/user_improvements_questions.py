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

    @router.message(Command('myimprovements'), StateFilter(None, States.message), UserFilter())
    async def get_my_improvements(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="feedback_ids",
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Feedback).filter(and_(
                            Feedback.telegram_user_id == message.from_user.id,
                            Feedback.type == "improvement"
                        ))
                    )
                    feedbacks = result.scalars().all()

                    if len(feedbacks) == 0:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Вы не пердлагали улучшений",
                            keyboard=kb.create_clear_feedback_keyboard(),
                            state_name="feedback_ids",
                        )
                        return

                    for feedback in feedbacks:
                        answer = "Пока нет ответа" if len(feedback.answer) == 0 else feedback.answer
                        text = f"<b>Ваше предложение</b>:\n{feedback.text}\n\n<b>Комментарий администратора:</b>\n{answer}"
                        await send_state_message(
                            state=state,
                            message=message,
                            text=text,
                            parse_mode=ParseMode.HTML,
                            state_name="feedback_ids",
                        )

                    await send_state_message(
                        state=state,
                        message=message,
                        text="Действия",
                        keyboard=kb.create_clear_feedback_keyboard(),
                        state_name="feedback_ids",
                    )
        except Exception as e:
            print(e)

    @router.message(Command('myquestions'), StateFilter(None, States.message), UserFilter())
    async def get_my_questions(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="feedback_ids",
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Feedback).filter(and_(
                            Feedback.telegram_user_id == message.from_user.id,
                            Feedback.type == "question"
                        ))
                    )
                    feedbacks = result.scalars().all()

                    if len(feedbacks) == 0:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Вы не задавали вопросов",
                            keyboard=kb.create_clear_feedback_keyboard(),
                            state_name="feedback_ids",
                        )
                        return

                    for feedback in feedbacks:
                        answer = "Пока нет ответа" if len(feedback.answer) == 0 else feedback.answer
                        text = f"<b>Ваш вопрос</b>:\n{feedback.text}\n\n<b>Ответ от администратора:</b>\n{answer}"
                        await send_state_message(
                            state=state,
                            message=message,
                            text=text,
                            parse_mode=ParseMode.HTML,
                            state_name="feedback_ids",
                        )

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
