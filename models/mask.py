from db import Base
from sqlalchemy import Column, BigInteger, Integer


# Таблица описывает маски для заявок от которых отказались пользователя
class Mask(Base):
    __tablename__ = 'mask'
    id: int = Column(Integer, primary_key=True)

    # ID заявки
    application_id: int = Column(Integer, nullable=False)

    # ID отказавшегося пользователя
    user_id: int = Column(Integer, nullable=False)

    # Telegram ID отказавшегося пользователя
    telegram_user_id: int = Column(BigInteger, nullable=False)
