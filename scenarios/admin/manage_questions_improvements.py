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

    async def manage_questions_improvements(message: types.Message, state: FSMContext, non_feedback_text, action_text, type_feedback):
        await add_state_id(
            state=state,
            message_id=message.message_id,
            state_name="feedback_admin_ids"
        )
        async with AsyncSessionLocal() as session:
            async with session.begin():

                result = await session.execute(
                    select(Feedback).filter(and_(
                        Feedback.type == type_feedback,
                        Feedback.answer == ""
                    ))
                )
                feedbacks = result.scalars().all()

                if len(feedbacks) == 0:
                    await send_state_message(
                        state=state,
                        message=message,
                        text=non_feedback_text,
                        state_name="feedback_admin_ids",
                        keyboard=kb.create_delete_admin_messages_keyboard()
                    )
                    return

                messages = []
                for feedback in feedbacks:
                    result = await session.execute(
                        select(User).filter(
                            User.telegram_user_id == feedback.telegram_user_id
                        )
                    )
                    user = result.scalars().first()

                    if user:
                        name = user.name
                    else:
                        name = "неизвестный пользователь"

                    text = f"<b>{action_text} {name}</b>\n\n{feedback.text}"
                    m = await send_state_message(
                        state=state,
                        message=message,
                        text=text,
                        keyboard=kb.create_answer_feedback_keyboard(),
                        parse_mode=ParseMode.HTML,
                        state_name="feedback_admin_ids",
                    )

                    messages.append({
                        'message_id': m.message_id,
                        'feedback': feedback.to_dict()
                    })

                state_feedback = {
                    'messages': messages,
                    'current_feedback': None,
                }

                await state.update_data(visible_feedbacks=state_feedback)

        await send_state_message(
            state=state,
            message=message,
            text="Действия",
            keyboard=kb.create_delete_admin_messages_keyboard(),
            state_name="feedback_admin_ids",
        )

    @router.message(Command('questions'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def get_feedback(message: types.Message, state: FSMContext):
        try:
            await manage_questions_improvements(
                message=message,
                state=state,
                non_feedback_text="Нет неотвеченных вопросов",
                action_text="Спрашивает",
                type_feedback="question"
            )
        except Exception as e:
            print(e)

    @router.message(Command('improvements'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def get_improvements(message: types.Message, state: FSMContext):
        try:
            await manage_questions_improvements(
                message=message,
                state=state,
                non_feedback_text="Нет предложений по улучшению",
                action_text="Предлагает",
                type_feedback="improvement"
            )
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.ANSWER_QUESTION_CALLBACK, UserFilter(check_admin=True))
    async def answer_question_callback(callback_query: types.CallbackQuery, state: FSMContext):
        try:
            data = await state.get_data()
            state_feedback: dict = data.get("visible_feedbacks", {})
            messages = state_feedback.get("messages", [])

            feedback = None
            for m in messages:
                if m['message_id'] == callback_query.message.message_id:
                    feedback = m['feedback']

            if feedback is None:
                print("Error")
                return

            state_feedback['current_feedback'] = feedback

            await send_state_message(
                state=state,
                message=callback_query.message,
                text="Введите ответ",
                state_name="feedback_admin_ids",
            )

            await state.update_data(visible_feedbacks=state_feedback)

            await state.set_state(States.visible_feedbacks)

        except Exception as e:
            print(e)

    @router.message(States.visible_feedbacks, UserFilter(check_admin=True))
    async def read_answer(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="feedback_admin_ids"
            )

            data = await state.get_data()
            state_feedback: dict = data.get("visible_feedbacks", {})
            feedback = state_feedback.get("current_feedback", None)

            if feedback is None:
                print("Error")
                return

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Feedback).filter(
                            Feedback.id == feedback['id']
                        )
                    )
                    feedback = result.scalars().first()

                    feedback.answer = message.text

                await session.commit()

            await send_state_message(
                state=state,
                message=message,
                text="Ответ сохранён",
                keyboard=kb.create_delete_admin_messages_keyboard(),
                state_name="feedback_admin_ids",
            )

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
