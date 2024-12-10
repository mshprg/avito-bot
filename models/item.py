from db import Base
from sqlalchemy import Column, BigInteger, Integer, String


# Таблица хранит записи об оьъявлениях с авито
class Item(Base):
    __tablename__ = 'item'
    id: int = Column(Integer, primary_key=True)

    # ID объявления на авито
    avito_item_id: int = Column(BigInteger, nullable=False)

    # Ссылка на объявление
    url: str = Column(String, nullable=False)

    # Локация объявления
    location: str = Column(String, nullable=False)
