from db import Base
from sqlalchemy import Column, BigInteger, Integer, String


class Confirmation(Base):
    __tablename__ = 'confirmation'
    id: int = Column(Integer, primary_key=True)
    telegram_user_id: int = Column(BigInteger, nullable=False)
    telegram_message_id: int = Column(BigInteger, nullable=False)
    amount: int = Column(Integer, nullable=False)
    created: int = Column(BigInteger, nullable=False)
    type: str = Column(String, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'telegram_user_id': self.telegram_user_id,
            'telegram_message_id': self.telegram_message_id,
            'amount': self.amount,
            'created': self.created,
            'type': self.type,
        }
