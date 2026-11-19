"""用 Redis 保存可撤销的访问会话，不保存 JWT 原文。"""

from datetime import datetime
from uuid import UUID

from redis.asyncio import Redis


def _session_key(user_id: UUID, session_id: UUID) -> str:
    return f"fastapi-new:auth:session:{session_id}:{user_id}"


async def activate(
    client: Redis, *, user_id: UUID, session_id: UUID, expires_at: datetime
) -> None:
    await client.set(_session_key(user_id, session_id), "1", exat=int(expires_at.timestamp()))


async def is_active(client: Redis, *, user_id: UUID, session_id: UUID) -> bool:
    return bool(await client.exists(_session_key(user_id, session_id)))


async def revoke(client: Redis, *, user_id: UUID, session_id: UUID) -> None:
    await client.delete(_session_key(user_id, session_id))


async def revoke_all(client: Redis, *, user_id: UUID, session_ids: list[UUID]) -> None:
    if session_ids:
        await client.delete(*(_session_key(user_id, session_id) for session_id in session_ids))
