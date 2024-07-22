from db import Base
from sqlalchemy import Column, Integer, String


class City(Base):
    __tablename__ = 'city'
    id: int = Column(Integer, primary_key=True)
    city: str = Column(String, nullable=False)
