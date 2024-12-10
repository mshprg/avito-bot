from db import Base
from sqlalchemy import Column, Integer, String, Boolean, BigInteger, Float


# Таблица описывает заявку в базе данных
class Application(Base):
    __tablename__ = 'application'
    id: int = Column(Integer, primary_key=True)\

    # ID чата на авито
    avito_chat_id: str = Column(String, nullable=False)

    # ID сообщения авито на котором была создана заявка
    avito_message_id: str = Column(String, nullable=False)

    # Статус заявки (работает ли кто-то над ней)
    in_working: bool = Column(Boolean, nullable=False, default=False)

    # Telegram ID пользователя, который работает наж заявкой (изначально = -1)
    working_user_id: int = Column(BigInteger, nullable=True)

    # Название объявления к которому принадлежит заявка
    item_name: str = Column(String, nullable=False)

    # Локация объявления
    item_location: str = Column(String, nullable=False)

    # ID объявления в базе данных
    item_id: int = Column(BigInteger, nullable=False)

    # Тип сообщения авито на котором была создана заявка
    type: str = Column(String, nullable=False)

    # Содержание сообщения авито на котором была создана заявка
    content: str = Column(String, nullable=False)

    # ID автора сообщения
    author_id: str = Column(String, nullable=False)
    user_id: str = Column(String, nullable=False)

    # Время создания заявки
    created: int = Column(BigInteger, nullable=False)

    # Время последнего сообщения
    last_message_time: int = Column(BigInteger, nullable=False)

    # Текст последнего сообщения
    last_message_text: str = Column(String, nullable=False)

    # Время закрытия заявки
    close_app_time: int = Column(BigInteger, nullable=False, default=-1)

    # Имя клиента
    username: str = Column(String, nullable=False)
