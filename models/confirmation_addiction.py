from db import Base
from sqlalchemy import Column, Integer, BigInteger


class ConfirmationAddiction(Base):
    __tablename__ = 'confirmation_addiction'
    id: int = Column(Integer, primary_key=True)
    confirmation_id: int = Column(Integer, nullable=False)
    telegram_message_id: int = Column(BigInteger, nullable=False)
    telegram_chat_id: int = Column(BigInteger, nullable=False)
