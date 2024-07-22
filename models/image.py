from db import Base
from sqlalchemy import Column, Integer, String


class Image(Base):
    __tablename__ = 'image'
    id: int = Column(Integer, primary_key=True)
    application_id: int = Column(Integer, nullable=False)
    file_name: str = Column(String, nullable=False)
