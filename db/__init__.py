"""数据库基础设施，不在包导入时创建连接引擎。"""

from .base import Base

__all__ = ["Base"]
