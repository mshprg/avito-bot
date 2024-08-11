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

    @router.message(F.text == "Обратная связь", UserFilter())
    async def send_feedback_callback(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="feedback_ids"
            )
            await send_state_message(
                state=state,
                message=message,
                text="*Действия:*",
                parse_mode=ParseMode.MARKDOWN_V2,
                keyboard=kb.create_feedback_actions_keyboard(),
                state_name="feedback_ids"
            )
        except Exception as e:
            print(e)

    async def send_feedback_message(text, type_feedback, callback_query: types.CallbackQuery, state: FSMContext):
        try:
            await send_state_message(
                state=state,
                message=callback_query.message,
                text=text,
                state_name="feedback_ids",
            )

            await state.update_data(feedback=type_feedback)
            await state.set_state(States.feedback)
        except Exception as e:
            print(e)

    @router.callback_query(F.data == callbacks.SEND_QUESTION_CALLBACK, UserFilter())
    async def send_question_callback(callback_query: types.CallbackQuery, state: FSMContext):
        await send_feedback_message(
            text="Отправьте вопрос",
            type_feedback="question",
            callback_query=callback_query,
            state=state
        )

    @router.callback_query(F.data == callbacks.SEND_IMPROVEMENT_CALLBACK, UserFilter())
    async def send_improvement_callback(callback_query: types.CallbackQuery, state: FSMContext):
        await send_feedback_message(
            text="Предложите улучшение",
            type_feedback="improvement",
            callback_query=callback_query,
            state=state
        )

    @router.message(States.feedback)
    async def read_feedback(message: types.Message, state: FSMContext):
        try:
            await add_state_id(
                state=state,
                message_id=message.message_id,
                state_name="feedback_ids"
            )
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    user_data = await state.get_data()
                    type_feedback = user_data.get("feedback", "None")
                    feedback = Feedback(
                        type=type_feedback,
                        text=message.text,
                        telegram_user_id=message.from_user.id
                    )

                    session.add(feedback)

                await session.commit()

            await send_state_message(
                state=state,
                message=message,
                text="Запрос отправлен",
                keyboard=kb.create_clear_feedback_keyboard(),
                state_name="feedback_ids",
            )
        except Exception as e:
            await send_state_message(
                state=state,
                message=message,
                text="Ошибка, введите текст заново",
                state_name="feedback_ids",
            )
            await state.set_state(States.feedback)
            print(e)

    dp.include_router(router)
