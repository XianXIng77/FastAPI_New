"""本地账号的数据库模型。"""

from uuid import UUID, uuid4

from sqlalchemy import Index, String, Uuid, func, true
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class User(Base):
    """存储登录账号及密码哈希。"""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=true())

    __table_args__ = (Index("uq_users_email_lower", func.lower(email), unique=True),)
