import time

from sqlalchemy import select

import kb
from models.payment import Payment
from robokassa.robokassa_api import result_payment, generate_payment_link
import config
from aiohttp import web
from db import AsyncSessionLocal


handled_operations = []


async def create_payment_link(amount, phone, telegram_user_id, telegram_message_id, application_id, type_payment,
                              type_action):
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    select(Payment)
                )
                payments = result.scalars().all()

                next_id = str(len(payments) + 1)

                number = int(next_id + (7 - len(next_id)) * "0")

                phone.replace("+", "")
                payment_link = generate_payment_link(
                    merchant_login=config.MERCHANT_LOGIN,
                    merchant_password_1=config.MERCHANT_PASSWORD_1,
                    cost=amount,
                    number=number,
                    description=phone.replace("+", "")
                )

                payment = Payment(
                    telegram_user_id=telegram_user_id,
                    telegram_message_id=telegram_message_id,
                    amount=amount,
                    created=int(time.time() * 1000),
                    number=number,
                    status=2,
                    application_id=application_id,
                    type=type_payment,
                    action=type_action,
                )

                session.add(payment)

            await session.commit()

        return payment_link
    except Exception as e:
        print(e)

    return None


async def check_status_payment(request):
    from main import bot
    try:
        res = await result_payment(config.MERCHANT_PASSWORD_2, request)
        if res == "bad sign":
            print("error - - - - - - - -- - - - \n-\n-\n-\n-\n")
            return
        number = int(res.replace("OK", ""))
        if number in handled_operations:
            return
        else:
            handled_operations.append(number)
        async with (AsyncSessionLocal() as session):
            async with session.begin():
                result = await session.execute(
                    select(Payment).filter(Payment.number == number)
                )
                payment = result.scalars().first()

                user_id = payment.telegram_user_id
                message_id = payment.telegram_message_id

                if payment.action == "open":
                    text = "Оплата подтверждена"
                    try:
                        await bot.edit_message_text(
                            chat_id=user_id,
                            message_id=message_id,
                            text=text,
                            reply_markup=kb.create_confirmation_keyboard()
                        )
                    except Exception as e:
                        await bot.send_message(
                            chat_id=user_id,
                            text=text,
                            reply_markup=kb.create_confirmation_keyboard()
                        )
                elif payment.action == "close":
                    text = "Оплата подтверждена"
                    try:
                        await bot.edit_message_text(
                            chat_id=user_id,
                            message_id=message_id,
                            text=text,
                            reply_markup=kb.create_close_application_keyboard()
                        )
                    except Exception as e:
                        await bot.send_message(
                            chat_id=user_id,
                            text=text,
                            reply_markup=kb.create_close_application_keyboard()
                        )

                payment.status = 0

            await session.commit()
    except Exception as e:
        print("Status payment error:", e)

    return web.json_response({"ok": True})
