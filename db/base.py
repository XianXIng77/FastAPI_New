"""数据库模型共享的声明式基类。"""

from sqlalchemy.orm import DeclarativeBase

# from datetime import datetime
# from sqlalchemy import DateTime, func
# from sqlalchemy.orm import Mapped, mapped_column


class Base(DeclarativeBase):
    """所有数据库模型的公共基类。

    导入子类后，SQLAlchemy 会把表结构登记到 Base.metadata，供 Alembic 生成迁移。
    定义模型只登记表结构，不会立即连接数据库或建表。
    """

    # 暂停注入公共时间字段，需要时再恢复字段和相关导入。
    # created_at: Mapped[datetime] = mapped_column(
    #     DateTime(timezone=True),
    #     nullable=False,
    #     server_default=func.now(),
    # )
    # updated_at: Mapped[datetime] = mapped_column(
    #     DateTime(timezone=True),
    #     nullable=False,
    #     server_default=func.now(),
    #     onupdate=func.now(),
    # )
