"""注册、登录、令牌刷新和退出的事务边界。"""

from datetime import datetime, timedelta, timezone
from sqlite3 import SQLITE_CONSTRAINT_UNIQUE
from uuid import UUID

from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from models import AuthSession, RefreshToken, User
from repositories import auth_session as auth_session_repository
from repositories import redis_session as redis_session_repository
from repositories import user as user_repository
from schemas.auth import LoginRequest, RegisterRequest, TokenPair


class AccountAlreadyExists(Exception):
    """邮箱或用户名已被使用。"""


class InvalidCredentials(Exception):
    """账号不存在、未启用或凭据无效。"""


class InvalidRefreshToken(Exception):
    """刷新令牌或关联会话已不可用。"""


async def register(session: AsyncSession, data: RegisterRequest) -> User:
    password_hash = await hash_password(data.password.get_secret_value())
    user = User(email=data.email.lower(), username=data.username, hashed_password=password_hash)
    try:
        async with session.begin():
            session.add(user)
    except IntegrityError as error:
        if (
            getattr(error.orig, "sqlstate", None) == "23505"
            or getattr(error.orig, "sqlite_errorcode", None) == SQLITE_CONSTRAINT_UNIQUE
        ):
            raise AccountAlreadyExists from error
        raise
    return user


async def login(
    session: AsyncSession, redis_client: Redis, data: LoginRequest, secret_key: SecretStr
) -> TokenPair:
    async with session.begin():
        user = await user_repository.get_by_email(session, data.email.lower())
        user_id = user.id if user is not None else None
        password_hash = user.hashed_password if user is not None else None

    valid_password = await verify_password(data.password.get_secret_value(), password_hash)
    if user_id is None or not valid_password:
        raise InvalidCredentials

    async with session.begin():
        user = await user_repository.get_for_update(session, user_id)
        if user is None or not user.is_active or user.hashed_password != password_hash:
            raise InvalidCredentials

        now = datetime.now(timezone.utc).replace(microsecond=0)
        auth_session = AuthSession(
            user_id=user_id, expires_at=now + timedelta(seconds=settings.auth_session_lifetime_seconds)
        )
        session.add(auth_session)
        await session.flush()
        tokens = _issue_token_pair(session, auth_session, secret_key=secret_key, now=now)
        await session.flush()
        await redis_session_repository.activate(
            redis_client, user_id=user_id, session_id=auth_session.id, expires_at=auth_session.expires_at
        )
    return tokens


async def refresh(
    session: AsyncSession, redis_client: Redis, token: str, secret_key: SecretStr
) -> TokenPair:
    """持有会话锁后重新读取旧令牌；发现重用时先提交撤销，再拒绝请求。"""
    if len(token) != 43 or not token.isascii():
        raise InvalidRefreshToken
    token_hash = hash_refresh_token(token)

    async with session.begin():
        auth_session = await auth_session_repository.lock_for_refresh(session, token_hash)
        if auth_session is None or auth_session.revoked_at is not None:
            raise InvalidRefreshToken

        previous_token = await session.get(RefreshToken, token_hash, populate_existing=True)
        if previous_token is None:
            raise InvalidRefreshToken

        now = datetime.now(timezone.utc)
        if _utc(auth_session.expires_at) <= now:
            raise InvalidRefreshToken
        if previous_token.consumed_at is not None:
            auth_session.revoked_at = now
            await redis_session_repository.revoke(
                redis_client, user_id=auth_session.user_id, session_id=auth_session.id
            )
        else:
            user = await session.get(User, auth_session.user_id, populate_existing=True)
            if user is None or not user.is_active or _utc(previous_token.expires_at) <= now:
                raise InvalidRefreshToken
            if not await redis_session_repository.is_active(
                redis_client, user_id=auth_session.user_id, session_id=auth_session.id
            ):
                raise InvalidRefreshToken
            previous_token.consumed_at = now
            return _issue_token_pair(session, auth_session, secret_key=secret_key, now=now)

    raise InvalidRefreshToken


async def logout(
    session: AsyncSession, redis_client: Redis, *, user_id: UUID, session_id: UUID
) -> None:
    """在持有数据库会话行锁时移除 Redis 会话，提交后再返回成功。"""
    async with session.begin():
        await auth_session_repository.revoke(
            session, user_id=user_id, session_id=session_id, now=datetime.now(timezone.utc)
        )
        await redis_session_repository.revoke(redis_client, user_id=user_id, session_id=session_id)


async def disable_user(session: AsyncSession, redis_client: Redis, *, user_id: UUID) -> bool:
    """停用账号并撤销全部会话；供通过权限校验的管理业务调用。"""
    async with session.begin():
        user = await user_repository.get_for_update(session, user_id)
        if user is None:
            return False
        user.is_active = False
        session_ids = await auth_session_repository.revoke_all_for_user(
            session, user_id=user_id, now=datetime.now(timezone.utc)
        )
        await redis_session_repository.revoke_all(redis_client, user_id=user_id, session_ids=session_ids)
    return True


def _issue_token_pair(
    session: AsyncSession,
    auth_session: AuthSession,
    *,
    secret_key: SecretStr,
    now: datetime,
) -> TokenPair:
    session_expires_at = _utc(auth_session.expires_at)
    issued_at = now.replace(microsecond=0)
    access_expires_at = min(
        issued_at + timedelta(seconds=settings.access_token_lifetime_seconds), session_expires_at
    )
    refresh_expires_at = min(
        now + timedelta(seconds=settings.refresh_token_lifetime_seconds), session_expires_at
    )
    refresh_token, token_hash = create_refresh_token()
    session.add(
        RefreshToken(token_hash=token_hash, session_id=auth_session.id, expires_at=refresh_expires_at)
    )
    return TokenPair(
        access_token=create_access_token(
            auth_session.user_id,
            auth_session.id,
            secret_key=secret_key,
            issued_at=issued_at,
            expires_at=access_expires_at,
        ),
        refresh_token=refresh_token,
        expires_in=int((access_expires_at - issued_at).total_seconds()),
    )


def _utc(timestamp: datetime) -> datetime:
    """内存测试使用的 SQLite 读回无时区值，按写入时的 UTC 解释。"""
    return timestamp.replace(tzinfo=timezone.utc) if timestamp.tzinfo is None else timestamp
