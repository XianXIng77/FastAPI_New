"""集中声明接口共用的依赖，避免每个接口重复定义。"""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security import InvalidAccessToken, decode_access_token
from db.session import get_db
from models import User
from repositories import auth_session as auth_session_repository


# 接口参数写 session: SessionDep，FastAPI 就会调用 get_db 提供会话。
# 复用的是依赖声明，每次请求仍然创建并关闭自己的会话。
SessionDep = Annotated[AsyncSession, Depends(get_db)]
_bearer = HTTPBearer(bearerFormat="JWT", auto_error=False)


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


async def get_current_user(identity: AccessTokenIdentityDep, session: SessionDep) -> User:
    """用会话状态和账号状态确认当前用户。"""
    user_id, session_id = identity
    async with session.begin():
        user = await auth_session_repository.get_active_user(
            session, user_id=user_id, session_id=session_id, now=datetime.now(timezone.utc)
        )
    if user is None:
        raise _unauthorized()
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
