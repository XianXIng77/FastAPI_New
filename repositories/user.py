from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import User


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(func.lower(User.email) == email))


async def get_active_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))


async def get_for_update(session: AsyncSession, user_id: UUID) -> User | None:
    statement = select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
    return await session.scalar(statement)
