import robokassa
from db import AsyncSessionLocal


async def create_payment_link():
    try:
        link = robokassa.generate_payment_link(
            merchant_login="Zayavka_easily",
            merchant_password_1="XXw6Hh5ZmXn4iKTr6Cv7",
            cost=1,
            number=100,
            is_test=1,
            description="test purchase"
        )
        async with AsyncSessionLocal() as session:
            async with session.begin():
                ...
    except Exception as e:
        print(e)


async def check_status_payment():
    ...

link = robokassa.generate_payment_link(
            merchant_login="Zayavka-easily",
            merchant_password_1="AfRcq6QlFu7xqghM18B6",
            cost=1,
            number=1,
            is_test=1,
            description="test purchase"
        )
print(link)
