from db import Base
from sqlalchemy import Column, BigInteger, Integer


class Subscription(Base):
    __tablename__ = 'subscription'
    id: int = Column(Integer, primary_key=True)
    telegram_user_id: int = Column(BigInteger, nullable=False)
    # 0 - work, 1 - frozen, 2 - empty, 3 - trial
    status: int = Column(Integer, nullable=False)
    end_time: int = Column(BigInteger, nullable=False, default=-1)

    def to_dict(self):
        return {
            'id': self.id,
            'telegram_user_id': self.telegram_user_id,
            'price': self.price,
            'status': self.status,
            'end_time': self.end_time,
        }
