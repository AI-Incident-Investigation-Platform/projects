from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db.enums import BuiltinRole
from src.core.db.models import Membership, Role
from src.main import container


async def add_member(db: AsyncSession, project_id: str, user_id: UUID, role: BuiltinRole) -> None:
    """Участник с ролью напрямую в БД, минуя приглашение: короче для тестов прав.

    Права проекта в Dragonfly сбрасываются: иначе записанный там отказ продержался
    бы до 5 секунд свежести.
    """
    role_id = await db.scalar(select(Role.id).where(Role.key == role))
    db.add(Membership(project_id=UUID(project_id), user_id=user_id, role_id=role_id))
    await db.commit()
    await (await container.get(Redis)).delete(f"projects:members:{project_id}")
