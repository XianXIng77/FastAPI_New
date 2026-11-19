from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuthSession, RefreshToken, User


async def get_active_user(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    now: datetime,
) -> User | None:
    """只返回仍启用且拥有有效会话的用户。"""
    statement = (
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            User.id == user_id,
            User.is_active.is_(True),
            AuthSession.id == session_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
    )
    return await session.scalar(statement)


async def lock_for_refresh(session: AsyncSession, token_hash: str) -> AuthSession | None:
    """锁定刷新令牌所属的会话，串行处理该会话的轮换和撤销。"""
    statement = (
        select(AuthSession)
        .join(RefreshToken, RefreshToken.session_id == AuthSession.id)
        .where(RefreshToken.token_hash == token_hash)
        .with_for_update(of=AuthSession)
        .execution_options(populate_existing=True)
    )
    return await session.scalar(statement)


async def revoke(
    session: AsyncSession,
    *,
    user_id: UUID,
    session_id: UUID,
    now: datetime,
) -> None:
    """只撤销指定用户的这一条会话，不覆盖已有撤销时间。"""
    statement = (
        update(AuthSession)
        .where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await session.execute(statement)
