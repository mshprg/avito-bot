from db import Base
from sqlalchemy import Column, BigInteger, Integer, String


class Payment(Base):
    __tablename__ = 'payment'
    id: int = Column(Integer, primary_key=True)
    telegram_user_id: int = Column(BigInteger, nullable=False)
    amount: int = Column(Integer, nullable=False)
    created: int = Column(BigInteger, nullable=False)
    number: int = Column(BigInteger, nullable=False)
    # 0 - success, 1 - fail, 2 - wait, 3 - return or wait for a return
    status: int = Column(Integer, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'telegram_user_id': self.telegram_user_id,
            'amount': self.amount,
            'created': self.created,
            'number': self.number,
            'status': self.status,
        }
