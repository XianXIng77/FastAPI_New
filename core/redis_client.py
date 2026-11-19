"""在应用生命周期内维护共享的异步 Redis 客户端。"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis
from redis.exceptions import RedisError

from core.config import Settings


logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def open_redis(config: Settings) -> AsyncIterator[Redis | None]:
    """未配置时跳过 Redis；配置后在启动时检查连接，退出时释放连接池。"""
    url = config.redis_url.get_secret_value().strip() if config.redis_url else ""
    if not url:
        logger.info("未配置 Redis 客户端（REDIS_URL 为空），跳过初始化。")
        yield None
        return

    try:
        client = Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=config.redis_connect_timeout_seconds,
            socket_timeout=config.redis_command_timeout_seconds,
            max_connections=config.redis_max_connections,
        )
    except ValueError:
        raise RuntimeError("REDIS_URL 无效，请检查连接配置。") from None

    async with client:
        try:
            await client.ping()
        except RedisError:
            raise RuntimeError("Redis 连接检查失败，请检查连接配置和服务状态。") from None
        logger.info("Redis 客户端初始化成功，连接检查通过。")
        yield client
