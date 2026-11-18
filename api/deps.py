"""集中声明接口共用的依赖，避免每个接口重复定义。"""

from typing import Annotated

from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.user import User


# 接口参数写 session: SessionDep，FastAPI 就会调用 get_db 提供会话。
# 复用的是依赖声明，每次请求仍然创建并关闭自己的会话。
SessionDep = Annotated[AsyncSession, Depends(get_db)]


async def get_user_db(session: SessionDep) -> SQLAlchemyUserDatabase:
    return SQLAlchemyUserDatabase(session, User)
