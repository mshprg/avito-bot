from aiogram import Bot, Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InputMediaVideo

import kb
from filters import UserFilter
from message_processing import send_state_media, send_state_message, add_state_id


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(F.text == "Обучающие видео", UserFilter())
    async def show_educational_videos(message: types.Message, state: FSMContext):

        await add_state_id(
            state=state,
            message_id=message.message_id,
            state_name="video_ids",
        )

        media = [
            InputMediaVideo(media='BAACAgIAAxkBAAIiWGbHYwABvQvMhSju-GRVEXM4p1VznQACm1UAAhiWOUqv8qdtGNZURjUE'),
            InputMediaVideo(media='BAACAgIAAxkBAAIiWWbHYwABGUVJsKzvRVA9JwSzwPCTrwACn1UAAhiWOUrhhGNy1_uKDDUE'),
            InputMediaVideo(media='BAACAgIAAxkBAAIiWmbHYwABnQ4eNSy5WYgbxsUmkWkq9wACo1UAAhiWOUoAAeFQv1rVYho1BA')
        ]

        await send_state_media(
            state=state,
            chat_id=message.chat.id,
            media=media,
            bot=bot,
            state_name="video_ids",
        )

        await send_state_message(
            state=state,
            message=message,
            text="Действия",
            keyboard=kb.create_clear_video_keyboard(),
            state_name="video_ids",
        )

    dp.include_router(router)
