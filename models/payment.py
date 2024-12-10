from db import Base
from sqlalchemy import Column, BigInteger, Integer, Text


class Payment(Base):
    __tablename__ = 'payment'
    id: int = Column(Integer, primary_key=True)

    # Telegram ID пользователя
    telegram_user_id: int = Column(BigInteger, nullable=False)

    # Сумма оплаты (руб)
    amount: int = Column(Integer, nullable=False)

    # Время создания
    created: int = Column(BigInteger, nullable=False)

    # Номер
    number: int = Column(BigInteger, nullable=False)

    # 0 - success, 1 - fail, 2 - wait, 3 - return or wait for a return
    status: int = Column(Integer, nullable=False)

    # Длительность тарифа за который платят
    duration: int = Column(Integer, nullable=False)

    # Описание тарифа за который платят
    description: str = Column(Text, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'telegram_user_id': self.telegram_user_id,
            'amount': self.amount,
            'created': self.created,
            'number': self.number,
            'status': self.status,
            'duration': self.duration,
        }
