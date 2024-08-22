from datetime import datetime, timedelta
from io import BytesIO

import pandas as pd
from aiogram.types import InputMediaDocument, BufferedInputFile
from sqlalchemy import select, and_

from db import AsyncSessionLocal
from main import bot
from message_processing import to_date
from models.application import Application
from models.user import User


async def generate_report():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(User).filter(User.admin == True)
            )

            users = result.scalars().all()

            now = datetime.now()
            yesterday_start = datetime(now.year, now.month, now.day) - timedelta(days=1)
            yesterday_end = datetime(now.year, now.month, now.day) + timedelta(days=1)

            yesterday_start_timestamp = int(yesterday_start.timestamp())
            yesterday_end_timestamp = int(yesterday_end.timestamp())

            report = await collect_data(session, yesterday_start_timestamp, yesterday_end_timestamp)

            await send_report(report, users, "За этот день нет новых заявок")

            if now.day == 1:
                last_month_end = datetime(now.year, now.month, 1) - timedelta(seconds=1)
                last_month_start = datetime(last_month_end.year, last_month_end.month, 1)

                last_month_end_timestamp = int(last_month_end.timestamp())
                last_month_start_timestamp = int(last_month_start.timestamp())

                report = await collect_data(session, last_month_start_timestamp, last_month_end_timestamp)

                await send_report(report, users, "За этот месяц нет новых заявок")


async def send_report(report, users, text_none):
    if report:
        for user in users:
            try:
                await bot.send_media_group(
                    chat_id=user.telegram_chat_id,
                    media=[report]
                )
            except:
                ...
    else:
        for user in users:
            try:
                await bot.send_message(
                    chat_id=user.telegram_chat_id,
                    text=text_none
                )
            except:
                ...


async def collect_data(session, start_unix, end_unix):
    result = await session.execute(
        select(Application).filter(
            and_(
                Application.created >= start_unix,
                Application.created <= end_unix,
            )
        )
    )
    applications = result.scalars().all()

    if len(applications) == 0:
        return None

    data = {
        "Наименование": [],
        "Телефон исполнителя": [],
        "Ф.И.О. Исполнителя": [],
        "Наименование Заказчика": [],
        "Последнее сообщение Заказчика": [],
        "Дата обращения Заказчика": [],
        "Дата последнего сообщения": [],
        "Заработано исполнителем": [],
        "Заработано вами": [],
    }

    names, phones, fio, usernames, last_messages, date_income, date_last_message, price, income = \
        [], [], [], [], [], [], [], [], []

    working_ids = [application.working_user_id for application in applications]

    result = await session.execute(
        select(User).filter(User.telegram_user_id.in_(working_ids))
    )
    users = result.scalars().all()

    for application in applications:
        user = next((u for u in users if u.telegram_user_id == application.working_user_id), None)

        if user is None:
            phones.append("-")
            fio.append("-")
        else:
            phones.append(user.phone)
            fio.append(user.name)

        if application.pay_type == "percent":
            res_price = application.price * (100 - application.com_value) / 100
        else:
            res_price = application.price - application.com_value

        names.append(application.item_name)
        usernames.append(application.username)
        last_messages.append(application.last_message_text)
        date_income.append(to_date(application.created))
        date_last_message.append(to_date(application.last_message_time))
        price.append(res_price)
        income.append(application.income)

    data['Наименование'] = names
    data['Телефон исполнителя'] = phones
    data['Ф.И.О. Исполнителя'] = fio
    data['Наименование Заказчика'] = usernames
    data['Последнее сообщение Заказчика'] = last_messages
    data['Дата обращения Заказчика'] = date_income
    data['Дата последнего сообщения'] = date_last_message
    data['Заработано исполнителем'] = price
    data['Заработано вами'] = income

    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Заявки')
    output.seek(0)
    excel_bytes = output.getvalue()

    if end_unix - start_unix >= 86400000 * 1.3:
        date_str = datetime.fromtimestamp(end_unix - 60 * 1000).strftime("%m-%Y")
    else:
        date_str = datetime.fromtimestamp(end_unix - 60 * 1000).strftime("%d-%m-%Y")

    report = InputMediaDocument(
        media=BufferedInputFile(
            excel_bytes,
            filename=f'report_{date_str}.xlsx'
        ),
    )

    return report
