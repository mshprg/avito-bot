from db import Base
from sqlalchemy import Column, Integer, BigInteger


# Таблица описывает взаимосвязь между заявкой в бд и сообщениями с ней у пользователей в чатах
class Addiction(Base):
    __tablename__ = 'addiction'

    id: int = Column(Integer, primary_key=True)

    # ID заявки
    application_id: int = Column(Integer, nullable=False)

    # ID сообщения
    telegram_message_id: int = Column(BigInteger, nullable=False)

    # ID чата
    telegram_chat_id: int = Column(BigInteger, nullable=False)
