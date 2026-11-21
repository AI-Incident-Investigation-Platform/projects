import logging
import time
from uuid import UUID

from aiip_kit.access.checker import AclCacheWriter
from aiip_kit.access.model import FRESHNESS_MS, AclSnapshot
from aiip_kit.errors import DependencyUnavailableError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.db.exc import DatabaseUnavailableError
from src.core.db.uow import UnitOfWork

log = logging.getLogger(__name__)

# удаления проекта ещё нет (PRJ-11): проект либо активен, либо его нет
ACTIVE_LIFECYCLE_VERSION = 1


class AclStore:
    """Права участника для других сервисов: снимок из БД и его запись в Dragonfly.

    Остальные сервисы читают права из Dragonfly, а при промахе или устаревании
    зовут `GET /internal/v1/acl`, который отдаёт тот же снимок. Запись живёт
    5 секунд (`fresh_until_ms`), поэтому даже упавшая запись после commit
    задерживает отзыв доступа не дольше этого срока.
    """

    def __init__(self, session_maker: async_sessionmaker[AsyncSession], redis: Redis) -> None:
        self._session_maker = session_maker
        self._writer = AclCacheWriter(redis)

    async def fetch(self, project_id: UUID, user_id: UUID) -> AclSnapshot:
        """Снимок из БД, заодно положенный в Dragonfly.

        Raises:
            DependencyUnavailableError: БД недоступна.
        """
        snapshot = await self._read(project_id, user_id)
        try:
            await self._writer.store(snapshot)
        except DependencyUnavailableError:
            # снимок верен и без кэша: следующая проверка снова придёт сюда
            log.warning(
                "Права не записаны в Dragonfly",
                extra={"event": "acl.store_failed", "project_id": str(project_id)},
            )
        return snapshot

    async def refresh(self, project_id: UUID, user_id: UUID) -> None:
        """Переписывает права в Dragonfly после commit изменения доступа.

        Ошибка не роняет запрос: изменение уже в БД, а старая запись устареет
        сама не позже чем через 5 секунд.
        """
        try:
            await self.fetch(project_id, user_id)
        except DependencyUnavailableError:
            log.warning(
                "Права после изменения не перечитаны",
                extra={"event": "acl.refresh_failed", "project_id": str(project_id)},
            )

    async def _read(self, project_id: UUID, user_id: UUID) -> AclSnapshot:
        # время чтения берётся до запроса: свежесть отсчитывается от самого раннего момента
        observed_at_ms = time.time_ns() // 1_000_000
        try:
            async with self._session_maker() as session:
                entry = await UnitOfWork(session).projects.get_acl(project_id, user_id)
        except DatabaseUnavailableError as exc:
            raise DependencyUnavailableError("postgres") from exc
        if entry is None:
            return AclSnapshot(
                project_id=project_id,
                user_id=user_id,
                project_state="missing",
                lifecycle_version=0,
                acl_version=0,
                member_role_key=None,
                member_version=None,
                role_key=None,
                role_version=None,
                permissions=frozenset(),
                observed_at_ms=observed_at_ms,
                fresh_until_ms=observed_at_ms + FRESHNESS_MS,
            )
        return AclSnapshot(
            project_id=project_id,
            user_id=user_id,
            project_state="active",
            lifecycle_version=ACTIVE_LIFECYCLE_VERSION,
            acl_version=entry.acl_version,
            member_role_key=entry.role_key,
            # членство версионируется версией доступа проекта, роль — своей
            member_version=entry.acl_version if entry.role_key is not None else None,
            role_key=entry.role_key,
            role_version=entry.role_version,
            permissions=frozenset(entry.permissions),
            observed_at_ms=observed_at_ms,
            fresh_until_ms=observed_at_ms + FRESHNESS_MS,
        )
