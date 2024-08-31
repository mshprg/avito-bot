from db import Base
from sqlalchemy import Column, Integer, BigInteger


class Work(Base):
    __tablename__ = 'work'
    id: int = Column(Integer, primary_key=True)
    application_id: int = Column(Integer, nullable=False, unique=True)
    telegram_user_id: int = Column(BigInteger, nullable=False, unique=True)
