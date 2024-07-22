from db import Base
from sqlalchemy import Column, Integer, BigInteger


class Addiction(Base):
    __tablename__ = 'addiction'
    id: int = Column(Integer, primary_key=True)
    application_id: int = Column(Integer, nullable=False)
    telegram_message_id: int = Column(BigInteger, nullable=False)
    telegram_chat_id: int = Column(BigInteger, nullable=False)
