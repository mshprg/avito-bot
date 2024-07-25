from db import Base
from sqlalchemy import Column, Integer, String, BigInteger


class Feedback(Base):
    __tablename__ = 'feedback'
    id: int = Column(Integer, primary_key=True)
    type: str = Column(String, nullable=False)
    text: str = Column(String, nullable=False)
    answer: str = Column(String, default="")
    telegram_user_id: int = Column(BigInteger, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'text': self.text,
            'telegram_user_id': self.telegram_user_id,
        }