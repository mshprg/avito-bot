import time

from sqlalchemy import select

from models.payment import Payment
from models.subscription import Subscription
from robokassa.robokassa_api import result_payment, generate_payment_link
import config
from aiohttp import web
from db import AsyncSessionLocal


handled_operations = []


async def create_payment_link(amount, phone, telegram_user_id):
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
                    description=phone.replace("+", ""),
                    is_test=1
                )

                payment = Payment(
                    telegram_user_id=telegram_user_id,
                    amount=amount,
                    created=int(time.time() * 1000),
                    number=number,
                    status=2,
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

                result = await session.execute(
                    select(Subscription).filter(Subscription.telegram_user_id == user_id)
                )
                subscription = result.scalars().first()

                if subscription is None:
                    subscription = Subscription(
                        telegram_user_id=user_id,
                        price=payment.amount,
                        status=2,
                        end_time=int(time.time() * 1000) + 86400000 * 30,
                    )
                    session.add(subscription)
                else:
                    if subscription.end_time == -1:
                        subscription.end_time = int(time.time() * 1000) + 86400000 * 30
                    else:
                        subscription.end_time += 86400000 * 30
                    subscription.status = 0

                payment.status = 0

                await bot.send_message(
                    chat_id=user_id,
                    text="Доступ продлён"
                )

            await session.commit()
    except Exception as e:
        print("Status payment error:", e)

    return web.json_response({"ok": True})
