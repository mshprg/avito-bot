from db import Base
from sqlalchemy import Column, BigInteger, Integer, String


class Item(Base):
    __tablename__ = 'item'
    id: int = Column(Integer, primary_key=True)
    avito_item_id: int = Column(BigInteger, nullable=False)
    url: str = Column(String, nullable=False)
    location: str = Column(String, nullable=False)
