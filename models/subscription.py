from db import Base
from sqlalchemy import Column, BigInteger, Integer


class Subscription(Base):
    __tablename__ = 'subscription'
    id: int = Column(Integer, primary_key=True)
    telegram_user_id: int = Column(BigInteger, nullable=False)
    price: int = Column(Integer, nullable=False)
    # 0 - work, 1 - frozen, 2 - empty
    status: int = Column(Integer, nullable=False)
    end_time: int = Column(BigInteger, nullable=False)
