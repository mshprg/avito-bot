from aiogram import types
from aiogram.filters import BaseFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

import config
from db import AsyncSessionLocal
from message_processing import send_state_message
from models.user import User


class UserFilter(BaseFilter):
    check_admin: bool = False

    def __init__(self, check_admin: bool = False):
        self.check_admin = check_admin

    async def __call__(self, obj: types.Update, state: FSMContext) -> bool:
        if isinstance(obj, types.Message) or isinstance(obj, types.CallbackQuery):
            user_id = obj.from_user.id

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(User).filter(User.telegram_user_id == user_id)
                    )
                    user = result.scalars().first()

                    if isinstance(obj, types.Message):
                        m = obj
                    else:
                        m = obj.message

                    if user is None:
                        return False

                    if user.banned and user.telegram_user_id not in config.ROOT_USER_IDS:
                        await send_state_message(
                            state=state,
                            message=m,
                            text="Вы были заблокированны администратором"
                        )
                        return False

                    if not user.admin and user.telegram_user_id not in config.ROOT_USER_IDS and self.check_admin:
                        await send_state_message(
                            state=state,
                            message=m,
                            text="Вы должны иметь права администратора"
                        )
                        return False

                    return True

        return False
