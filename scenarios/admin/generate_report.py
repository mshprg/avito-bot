import calendar
import time
from datetime import datetime

from aiogram import Bot, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from db import AsyncSessionLocal
from filters import UserFilter
from message_processing import reset_state, send_state_message
from models.user import User
from states import States


def load_handlers(dp, bot: Bot):
    router = Router()

    @router.message(Command('report'), StateFilter(None, States.message), UserFilter(check_admin=True))
    async def generate_report(message: types.Message, state: FSMContext):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():

                    result = await session.execute(
                        select(User).filter(User.telegram_user_id == message.from_user.id)
                    )
                    user = result.scalars().first()

                    if user is None:
                        return

                    if not user.admin:
                        await send_state_message(
                            state=state,
                            message=message,
                            text="Вы должны иметь права администратора"
                        )
                        return

                    await send_state_message(
                        state=state,
                        message=message,
                        text="Если вы желаете сгенерировать отчёт за день \- введите дату в формате *ДД\.ММ\.ГГГГ*\nЕсли "
                             "вы желаете сгенерировать отчёт за месяц \- введите дату в формате *ММ\.ГГГГ*",
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                    await state.set_state(States.report_date)
        except Exception as e:
            print(e)

    @router.message(States.report_date, UserFilter(check_admin=True))
    async def read_report_date(message: types.Message, state: FSMContext):
        from report import collect_data
        try:
            date_str = message.text

            start_unix, end_unix = None, None

            try:
                date_obj = datetime.strptime(date_str, '%m.%Y')

                start_of_month = datetime(date_obj.year, date_obj.month, 1)
                start_unix = int(time.mktime(start_of_month.timetuple()))

                _, last_day = calendar.monthrange(date_obj.year, date_obj.month)
                end_of_month = datetime(date_obj.year, date_obj.month, last_day, 23, 59, 59)
                end_unix = int(time.mktime(end_of_month.timetuple()))
            except ValueError:
                pass

            try:
                date_obj = datetime.strptime(date_str, '%d.%m.%Y')

                start_of_day = datetime(date_obj.year, date_obj.month, date_obj.day)
                start_unix = int(time.mktime(start_of_day.timetuple()))

                end_of_day = datetime(date_obj.year, date_obj.month, date_obj.day, 23, 59, 59)
                end_unix = int(time.mktime(end_of_day.timetuple()))
            except ValueError:
                pass

            if start_unix is not None and end_unix is not None:
                async with AsyncSessionLocal() as session:
                    async with session.begin():

                        report = await collect_data(session, start_unix, end_unix)

                        if report:
                            await bot.send_media_group(
                                chat_id=message.chat.id,
                                media=[report]
                            )
                        else:
                            await bot.send_message(
                                chat_id=message.chat.id,
                                text="За данный период нет новых заявок"
                            )

            await reset_state(state)

        except Exception as e:
            print(e)

    dp.include_router(router)
