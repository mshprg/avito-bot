from sqlalchemy import Column, Integer, String, Text

from db import Base


class Tariff(Base):
    __tablename__ = 'tariffs'

    # ID записи
    id: int = Column(Integer, primary_key=True)

    # Длительность в месяцах
    duration: int = Column(Integer, unique=True)

    # Цена тарифа
    price: int = Column(Integer, nullable=False)

    # Описание тарифа
    description: str = Column(Text, nullable=False)

    # Перевод записи в словарь
    def to_dict(self):
        return {
            'id': self.id,
            'duration': self.duration,
            'price': self.price,
            'description': self.description,
        }