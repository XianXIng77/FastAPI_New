"""测试使用独立内存数据库，不读取或写入用户的 PostgreSQL 数据。"""

import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


# 在应用导入前覆盖连接配置，即便误用正式依赖也不会连接项目配置的数据库。
# 实际 HTTP 测试还会通过 dependency_overrides 替换数据库会话。
os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://test_user:test_password@127.0.0.1:5432/test_db"
)

from db.base import Base
from db.session import get_db
from main import app


@pytest.fixture
def anyio_backend():
    """SQLAlchemy 的异步驱动在这些测试中使用 asyncio。"""
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """每个测试创建独立数据库，验证真实 SQL、事务及持久化结果。"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture
async def client(session_factory) -> AsyncIterator[AsyncClient]:
    """保留真实路由和业务逻辑，只把数据库会话替换成测试会话。"""
    async def override_get_db():
        async with session_factory() as session:
            yield session

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
