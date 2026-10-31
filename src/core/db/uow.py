from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db.repositories.api_token import ApiTokenRepository
from src.core.db.repositories.environment import EnvironmentRepository
from src.core.db.repositories.invitation import InvitationRepository
from src.core.db.repositories.membership import MembershipRepository
from src.core.db.repositories.monitored_service import MonitoredServiceRepository
from src.core.db.repositories.project import ProjectRepository
from src.core.db.repositories.role import RoleRepository


class UnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.projects = ProjectRepository(self._session)
        self.roles = RoleRepository(self._session)
        self.memberships = MembershipRepository(self._session)
        self.environments = EnvironmentRepository(self._session)
        self.services = MonitoredServiceRepository(self._session)
        self.api_tokens = ApiTokenRepository(self._session)
        self.invitations = InvitationRepository(self._session)

    async def ping(self) -> None:
        await self._session.execute(text("SELECT 1"))

    async def flush(self) -> None:
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
