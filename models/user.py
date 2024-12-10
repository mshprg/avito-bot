from db import Base
from sqlalchemy import Column, Integer, String, Boolean, BigInteger


class User(Base):
    __tablename__ = 'user'
    id: int = Column(Integer, primary_key=True)

    # Telegram ID пользователя
    telegram_user_id: int = Column(BigInteger, nullable=False, unique=True)

    # ID чата с пользователем
    telegram_chat_id: int = Column(BigInteger, nullable=False, unique=True)

    # Номер телефона пользователя
    phone: str = Column(String, nullable=False, unique=True)

    # ФИО пользователя
    name: str = Column(String, nullable=False)

    # Локация пользователя
    city: str = Column(String, nullable=False)

    # Статус пользователя (работает или нет)
    in_working: bool = Column(Boolean, nullable=False, default=False)

    # Является ли пользователь админом
    admin: bool = Column(Boolean, nullable=False, default=False)

    # Заблокирован ли пользователь
    banned: bool = Column(Boolean, nullable=False, default=False)

    # Массив сообщений который пользователь отправил в чат авито во время работы с заявкой
    income_message_ids: str = Column(String, nullable=False, default="[]")

    # Время создарния пользователя
    created: int = Column(BigInteger, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'telegram_user_id': self.telegram_user_id,
            'telegram_chat_id': self.telegram_chat_id,
            'phone': self.phone,
            'name': self.name,
            'city': self.city,
            'in_working': self.in_working,
            'admin': self.admin,
            'banned': self.banned,
        }
