from collections.abc import Sequence

from sqlalchemy import func, select

from src.core.db.models.role import Role
from src.core.db.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    model = Role

    async def get_by_key(self, key: str) -> Role | None:
        return await self._session.scalar(select(Role).where(Role.key == key))

    async def list_all(self) -> Sequence[Role]:
        # от широкой роли к узкой: owner, admin, developer, viewer
        query = select(Role).order_by(func.cardinality(Role.permissions).desc(), Role.key)
        return (await self._session.scalars(query)).all()
