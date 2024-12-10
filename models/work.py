from db import Base
from sqlalchemy import Column, Integer, BigInteger


# Таблица описывает связь между заявкой и работающим пользователем
# Если запись существует, то пользовател с telegram_user_id работает над заявкой application_id в данный момент
class Work(Base):
    __tablename__ = 'work'
    id: int = Column(Integer, primary_key=True)

    # ID заявки
    application_id: int = Column(Integer, nullable=False, unique=True)

    # Telegram ID пользователя
    telegram_user_id: int = Column(BigInteger, nullable=False, unique=True)
