import json
import logging
import time
from datetime import UTC
from typing import Any

from aiip_kit.api_tokens.reader import TOKEN_PREFIX
from aiip_kit.errors import DependencyUnavailableError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.access.acl import ACTIVE_LIFECYCLE_VERSION
from src.core.db.exc import DatabaseUnavailableError
from src.core.db.models.api_token import ApiToken
from src.core.db.uow import UnitOfWork

log = logging.getLogger(__name__)

FRESHNESS_MS = 5_000
UNKNOWN_FRESHNESS_MS = 1_000
CACHE_TTL_SECONDS = 600
# отзыв необратим, поэтому версия токена выводится из состояния, а не хранится
ACTIVE_VERSION = 1
REVOKED_VERSION = 2

# KEYS: projects:token:<sha256>. ARGV: запись JSON, TTL.
# Запись принимается при большей версии или той же, но более позднем чтении из БД.
STORE = """
local current = redis.call('GET', KEYS[1])
local candidate = cjson.decode(ARGV[1])
if current then
  local stored = cjson.decode(current)
  if stored.ver > candidate.ver then return 0 end
  if stored.ver == candidate.ver and stored.observed_at_ms >= candidate.observed_at_ms then
    return 0
  end
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', tonumber(ARGV[2]))
return 1
"""


class ApiTokenCache:
    """API-токены ingest в Dragonfly (`backend/decisions.md`, пункт 2).

    `ingest` читает `projects:token:<sha256>`, а при промахе или устаревании зовёт
    `GET /internal/v1/api-tokens/{sha256}` — тот же снимок. Запись свежа 5 секунд
    и не дольше срока токена, поэтому упавшая запись после отзыва держит токен
    живым не дольше 5 секунд. Неизвестный digest — отрицательная запись на секунду.
    """

    def __init__(self, session_maker: async_sessionmaker[AsyncSession], redis: Redis) -> None:
        self._session_maker = session_maker
        self._store = redis.register_script(STORE)

    async def fetch(self, token_hash: str) -> dict[str, Any] | None:
        """Снимок токена из БД, заодно положенный в Dragonfly; неизвестный — `None`.

        Raises:
            DependencyUnavailableError: БД недоступна.
        """
        observed_at_ms = time.time_ns() // 1_000_000
        try:
            async with self._session_maker() as session:
                token = await UnitOfWork(session).api_tokens.get_by_hash(token_hash)
        except DatabaseUnavailableError as exc:
            raise DependencyUnavailableError("postgres") from exc
        snapshot = (
            self._snapshot(token, observed_at_ms)
            if token is not None
            else {
                "state": "unknown",
                "ver": 0,
                "observed_at_ms": observed_at_ms,
                "fresh_until_ms": observed_at_ms + UNKNOWN_FRESHNESS_MS,
            }
        )
        try:
            await self._store(
                keys=[f"{TOKEN_PREFIX}{token_hash}"],
                args=[json.dumps(snapshot), CACHE_TTL_SECONDS],
            )
        except RedisError:
            # снимок верен и без кэша: следующая проверка снова придёт сюда
            log.warning(
                "API-токен не записан в Dragonfly", extra={"event": "api_token.store_failed"}
            )
        return snapshot if token is not None else None

    async def refresh(self, token_hash: str) -> None:
        """После commit выпуска или отзыва: ошибка не роняет запрос, запись устареет сама."""
        try:
            await self.fetch(token_hash)
        except DependencyUnavailableError:
            log.warning(
                "API-токен после изменения не перечитан",
                extra={"event": "api_token.refresh_failed"},
            )

    @staticmethod
    def _snapshot(token: ApiToken, observed_at_ms: int) -> dict[str, Any]:
        fresh_until_ms = observed_at_ms + FRESHNESS_MS
        state = "active"
        if token.revoked_at is not None:
            state = "revoked"
        elif token.expires_at is not None:
            expires_at_ms = int(token.expires_at.timestamp() * 1000)
            if expires_at_ms <= observed_at_ms:
                state = "expired"
            else:
                # истёкший токен не должен жить в кэше ни миллисекунды дольше срока
                fresh_until_ms = min(fresh_until_ms, expires_at_ms)
        return {
            "state": state,
            "token_id": str(token.id),
            "project_id": str(token.project_id),
            "environment_id": str(token.environment_id) if token.environment_id else None,
            "scopes": sorted(token.scopes),
            "lifecycle_version": ACTIVE_LIFECYCLE_VERSION,
            "ver": REVOKED_VERSION if token.revoked_at is not None else ACTIVE_VERSION,
            "expires_at": token.expires_at.astimezone(UTC).isoformat()
            if token.expires_at
            else None,
            "observed_at_ms": observed_at_ms,
            "fresh_until_ms": fresh_until_ms,
        }
