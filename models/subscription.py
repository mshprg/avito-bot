from db import Base
from sqlalchemy import Column, BigInteger, Integer, Text


class Subscription(Base):
    __tablename__ = 'subscription'

    # ID записи
    id: int = Column(Integer, primary_key=True)

    # Telegram ID пользователя, которому принадлежит подписка
    telegram_user_id: int = Column(BigInteger, nullable=False)

    # Длительность в месяцах
    duration: int = Column(Integer, nullable=False)

    # Описание тарифа
    description: str = Column(Text, nullable=False)

    # Время окончания подписки
    end_time: int = Column(BigInteger, nullable=False, default=-1)

    def to_dict(self):
        return {
            'id': self.id,
            'telegram_user_id': self.telegram_user_id,
            'duration': self.duration,
            'description': self.description,
            'end_time': self.end_time,
        }
