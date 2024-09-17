from db import Base
from sqlalchemy import Column, Integer, Float


class Shop(Base):
    __tablename__ = 'shop'
    id: int = Column(Integer, primary_key=True)
    subscribe_30days: float = Column(Float, nullable=False)
