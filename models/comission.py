from db import Base
from sqlalchemy import Column, Integer, Float


class Commission(Base):
    __tablename__ = 'commission'
    id: int = Column(Integer, primary_key=True)
    fixed: float = Column(Float, nullable=False)
    percent: float = Column(Float, nullable=False)
