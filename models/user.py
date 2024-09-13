from db import Base
from sqlalchemy import Column, Integer, String, Boolean, BigInteger


class User(Base):
    __tablename__ = 'user'
    id: int = Column(Integer, primary_key=True)
    telegram_user_id: int = Column(BigInteger, nullable=False, unique=True)
    telegram_chat_id: int = Column(BigInteger, nullable=False, unique=True)
    phone: str = Column(String, nullable=False, unique=True)
    name: str = Column(String, nullable=False)
    city: str = Column(String, nullable=False)
    in_working: bool = Column(Boolean, nullable=False, default=False)
    is_subscribed: bool = Column(Boolean, nullable=False, default=False)
    admin: bool = Column(Boolean, nullable=False, default=False)
    banned: bool = Column(Boolean, nullable=False, default=False)
    income_message_ids: str = Column(String, nullable=False, default="[]")

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
