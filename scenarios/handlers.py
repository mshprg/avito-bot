from aiogram import Router, types, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_
from applications import send_message_for_application
from db import AsyncSessionLocal
from filters import UserFilter
from models.application import Application
from states import States
from message_processing import add_state_id


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(States.message, UserFilter())
    async def send_message(message: types.Message, state: FSMContext):
        try:
            if message.media_group_id or message.photo or message.video:
                await bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                )
                await state.set_state(States.message)
                return

            text = message.text

            await add_state_id(state, message.message_id)

            data = await state.get_data()
            avito_info = data.get("avito_info", None)

            if avito_info is None:
                async with AsyncSessionLocal() as session:
                    async with session.begin():
                        result = await session.execute(
                            select(Application).filter(and_(
                                Application.working_user_id == message.from_user.id,
                                Application.in_working == True
                            ))
                        )
                        application = result.scalars().first()

                        avito_chat_id = str(application.avito_chat_id)
                        avito_user_id = str(application.user_id)

                        await state.update_data(avito_info={
                            'chat_id': avito_chat_id,
                            'user_id': avito_user_id,
                        })
            else:
                avito_chat_id = avito_info['chat_id']
                avito_user_id = avito_info['user_id']

            await send_message_for_application(
                avito_user_id=avito_user_id,
                avito_chat_id=avito_chat_id,
                text=text,
            )
        except Exception as e:
            print(e)
            await state.set_state(States.message)

    @router.message(Command('file'), StateFilter("*"))
    async def test_command(message: types.Message, state: FSMContext):
        await state.set_state(States.test_file)

    @router.message(States.test_file)
    async def test_file(message: types.Message, state: FSMContext):
        print(message.video)

    dp.include_router(router)
