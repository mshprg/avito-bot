from db import Base
from sqlalchemy import Column, Integer, String


# Таблица описывает все достпуные локации
class City(Base):
    __tablename__ = 'city'
    id: int = Column(Integer, primary_key=True)

    # Название локации (города)
    city: str = Column(String, nullable=False)
