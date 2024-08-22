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
            InputMediaVideo(media='BAACAgIAAxkBAAIcFmbHzfVmDRjILdprqCvC0qafunmUAAJxTAACRedAStenQseCZodmNQQ'),
            InputMediaVideo(media='BAACAgIAAxkBAAIcF2bHzfVnkMcmL3B6vL0G5ip3oLJFAAJyTAACRedASmeuxIUdxcoMNQQ'),
            InputMediaVideo(media='BAACAgIAAxkBAAIcGGbHzfVI-phdmyBpkLeW3eIdjK0FAAJzTAACRedASv7gevgwIDWFNQQ')
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
