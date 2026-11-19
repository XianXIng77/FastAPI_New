"""集中声明接口共用的依赖，避免每个接口重复定义。"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security import InvalidAccessToken, decode_access_token
from db.session import get_db
from models import User
from repositories import redis_session as redis_session_repository
from repositories import user as user_repository


# 接口参数写 session: SessionDep，FastAPI 就会调用 get_db 提供会话。
# 复用的是依赖声明，每次请求仍然创建并关闭自己的会话。
SessionDep = Annotated[AsyncSession, Depends(get_db)]
_bearer = HTTPBearer(bearerFormat="JWT", auto_error=False)


async def get_redis(request: Request) -> Redis:
    """获取应用已初始化的共享 Redis 客户端。"""
    client = getattr(request.app.state, "redis", None)
    if client is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis 未配置")
    return client


RedisDep = Annotated[Redis, Depends(get_redis)]


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="缺少或无效的访问令牌",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_access_token_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> tuple[UUID, UUID]:
    """验证 JWT 并获取用户 ID 和会话 ID，不查询会话状态。"""
    if credentials is None:
        raise _unauthorized()
    secret_key = settings.jwt_secret_key
    if secret_key is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="登录服务尚未配置")

    try:
        return decode_access_token(credentials.credentials, secret_key)
    except InvalidAccessToken as error:
        raise _unauthorized() from error


AccessTokenIdentityDep = Annotated[tuple[UUID, UUID], Depends(get_access_token_identity)]


async def get_current_session(
    identity: AccessTokenIdentityDep, redis_client: RedisDep
) -> tuple[UUID, UUID]:
    """验证 Redis 中的登录会话，返回用户 ID 和会话 ID，不查 PostgreSQL。"""
    user_id, session_id = identity
    if not await redis_session_repository.is_active(
        redis_client, user_id=user_id, session_id=session_id
    ):
        raise _unauthorized()
    return identity


CurrentSessionDep = Annotated[tuple[UUID, UUID], Depends(get_current_session)]


async def get_current_user(identity: CurrentSessionDep, session: SessionDep) -> User:
    """需要用户资料时才读取账号，并确认账号仍启用。"""
    user_id, _session_id = identity
    async with session.begin():
        user = await user_repository.get_active_by_id(session, user_id)
    if user is None:
        raise _unauthorized()
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
