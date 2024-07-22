from db import Base
from sqlalchemy import Column, Integer


class Commission(Base):
    __tablename__ = 'commission'
    id: int = Column(Integer, primary_key=True)
    fixed: int = Column(Integer, nullable=False)
    percent: int = Column(Integer, nullable=False)
