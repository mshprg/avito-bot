from db import Base
from sqlalchemy import Column, Integer, String


class Requisites(Base):
    __tablename__ = 'requisites'
    id: int = Column(Integer, primary_key=True)
    card_number: str = Column(String, nullable=False)
