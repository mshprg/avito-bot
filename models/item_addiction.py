from db import Base
from sqlalchemy import Column, Integer, BigInteger


class ItemAddiction(Base):
    __tablename__ = 'item_addiction'
    id: int = Column(Integer, primary_key=True)
    item_id: int = Column(Integer, nullable=False)
    telegram_message_id: int = Column(BigInteger, nullable=False)
    telegram_chat_id: int = Column(BigInteger, nullable=False)
