from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings


# 引擎管理连接池；导入模块时不会立即连接数据库。
async_engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    pool_pre_ping=settings.db_pool_pre_ping,
    max_overflow=settings.db_max_overflow,
)

# 每次调用工厂会生成独立会话；提交后保留已加载属性，方便异步场景读取。
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    expire_on_commit=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """为每次请求提供独立会话，结束时关闭；业务代码显式提交事务。"""
    async with AsyncSessionLocal() as session:
        yield session
