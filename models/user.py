"""基于 FastAPI Users 扩展的用户表模型。"""

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    """
    用户表模型（默认表名为 "user"）。

    已由父类自动提供的字段：
    - SQLAlchemyBaseUserTableUUID: id(UUID), email, hashed_password, is_active, is_superuser, is_verified
    - Base: created_at, updated_at
    """

    # 用户名：非空、唯一、建索引（方便后续支持用户名登录/查询）
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="用户名",
    )

    # 手机号：预留国际区号长度，允许为空；填写时保证唯一（PostgreSQL 唯一索引允许多个 NULL）
    phone: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=True,
        comment="手机号",
    )
