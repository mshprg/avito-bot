from db import Base
from sqlalchemy import Column, BigInteger, Integer


class Mask(Base):
    __tablename__ = 'mask'
    id: int = Column(Integer, primary_key=True)
    application_id: int = Column(Integer, nullable=False)
    user_id: int = Column(Integer, nullable=False)
    telegram_user_id: int = Column(BigInteger, nullable=False)
