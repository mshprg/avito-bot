from db import Base
from sqlalchemy import Column, BigInteger, Integer, TIMESTAMP, String


class Code(Base):
    __tablename__ = 'code'
    id: int = Column(Integer, primary_key=True)
    telegram_user_id: int = Column(BigInteger, nullable=False)
    code: int = Column(Integer, nullable=False)
    created: int = Column(BigInteger, nullable=False)
    code_type: str = Column(String, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'telegram_user_id': self.telegram_user_id,
            'code': self.code,
            'created': self.created,
            'code_type': self.code_type,
        }
