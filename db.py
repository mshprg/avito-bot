import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import config

# Создание базы даных

Base = declarative_base()
engine = create_async_engine(config.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    class_=AsyncSession,
    bind=engine,
)


# Инициализация бд
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Удаление всех просроченных подписок
async def delete_expired_subscriptions():
    from models.subscription import Subscription
    async with AsyncSessionLocal() as session:
        try:
            # Текущее время в миллисекундах
            current_time_ms = int(time.time() * 1000)

            # Удаление устаревших записей
            query = select(Subscription).where(Subscription.end_time < current_time_ms)
            results = await session.execute(query)
            expired_subscriptions = results.scalars().all()

            for subscription in expired_subscriptions:
                await session.delete(subscription)
            await session.commit()

            print(f"Удалено {len(expired_subscriptions)} устаревших подписок")
        except Exception as e:
            print(f"Ошибка: {e}")
