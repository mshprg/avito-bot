from db import Base
from sqlalchemy import Column, Integer, String, BigInteger


# Таблица с обратной связью от пользователей
class Feedback(Base):
    __tablename__ = 'feedback'
    id: int = Column(Integer, primary_key=True)

    # Тип обратной связи
    type: str = Column(String, nullable=False)

    # Текст обратной связи
    text: str = Column(String, nullable=False)

    # Ответ от админа
    answer: str = Column(String, default="")

    # Telegram ID отправителя
    telegram_user_id: int = Column(BigInteger, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'text': self.text,
            'telegram_user_id': self.telegram_user_id,
        }