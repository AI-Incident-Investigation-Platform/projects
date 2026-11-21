from typing import Any

from aiip_kit import errors as kit
from aiip_kit.api_tokens.reader import TOKENS_SCOPE
from aiip_kit.service_auth.verifier import ServiceTokenVerifier

from src.api.exc.ingest_tokens import IngestTokenNotFoundError
from src.core.access.exc import AccessUnavailableError
from src.core.api_tokens.cache import ApiTokenCache
from src.core.security.exc import NotAuthenticatedError, ServiceScopeDeniedError


class IngestTokenService:
    """API-токен проекта по его SHA-256 для `ingest`: промах его кэша в Dragonfly."""

    def __init__(self, verifier: ServiceTokenVerifier, cache: ApiTokenCache) -> None:
        self._verifier = verifier
        self._cache = cache

    async def get(self, authorization: str | None, token_hash: str) -> dict[str, Any]:
        """Снимок токена из БД; заодно кладёт его в Dragonfly.

        Raises:
            NotAuthenticatedError: нет служебного токена или он не прошёл проверку — 401.
            ServiceScopeDeniedError: у сервиса нет `projects.tokens.read` — 403.
            IngestTokenNotFoundError: токена с таким digest нет — 404.
            AccessUnavailableError: БД недоступна — 503.
        """
        try:
            await self._verifier.verify(authorization, TOKENS_SCOPE)
        except kit.NotAuthenticatedError as exc:
            raise NotAuthenticatedError({"reason": "service_token"}) from exc
        except kit.PermissionDeniedError as exc:
            raise ServiceScopeDeniedError({"scope": TOKENS_SCOPE}) from exc
        try:
            snapshot = await self._cache.fetch(token_hash)
        except kit.DependencyUnavailableError as exc:
            raise AccessUnavailableError({"dependency": exc.dependency}) from exc
        if snapshot is None:
            raise IngestTokenNotFoundError
        return snapshot
