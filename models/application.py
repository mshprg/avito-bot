from db import Base
from sqlalchemy import Column, Integer, String, Boolean, BigInteger, Float


class Application(Base):
    __tablename__ = 'application'
    id: int = Column(Integer, primary_key=True)
    avito_chat_id: str = Column(String, nullable=False)
    avito_message_id: str = Column(String, nullable=False)
    in_working: bool = Column(Boolean, nullable=False, default=False)
    working_user_id: int = Column(BigInteger, nullable=True)
    item_name: str = Column(String, nullable=False)
    item_location: str = Column(String, nullable=False)
    item_id: int = Column(BigInteger, nullable=False)
    type: str = Column(String, nullable=False)
    content: str = Column(String, nullable=False)
    author_id: str = Column(String, nullable=False)
    user_id: str = Column(String, nullable=False)
    created: int = Column(BigInteger, nullable=False)
    last_message_time: int = Column(BigInteger, nullable=False)
    last_message_text: str = Column(String, nullable=False)
    close_app_time: int = Column(BigInteger, nullable=False, default=-1)
    username: str = Column(String, nullable=False)
