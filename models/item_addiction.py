from db import Base
from sqlalchemy import Column, Integer, BigInteger


# Таблица описывает зависимость между записью объявления в бд и уведомлением о новом объявлении
# в чате телеграма
class ItemAddiction(Base):
    __tablename__ = 'item_addiction'
    id: int = Column(Integer, primary_key=True)

    # ID объявление в бд
    item_id: int = Column(Integer, nullable=False)

    # ID сообщения-уведомления
    telegram_message_id: int = Column(BigInteger, nullable=False)

    # ID чата
    telegram_chat_id: int = Column(BigInteger, nullable=False)
