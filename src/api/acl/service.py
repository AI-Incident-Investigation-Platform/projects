from uuid import UUID

from aiip_kit import errors as kit
from aiip_kit.access.model import AclSnapshot
from aiip_kit.access.source import ACL_SCOPE
from aiip_kit.service_auth.verifier import ServiceTokenVerifier

from src.core.access.acl import AclStore
from src.core.access.exc import AccessUnavailableError
from src.core.security.exc import NotAuthenticatedError, ServiceScopeDeniedError


class AclService:
    """Права участника для проверки в других сервисах: промах их кэша в Dragonfly."""

    def __init__(self, verifier: ServiceTokenVerifier, acl: AclStore) -> None:
        self._verifier = verifier
        self._acl = acl

    async def get(self, authorization: str | None, project_id: UUID, user_id: UUID) -> AclSnapshot:
        """Снимок прав из БД; заодно кладёт его в Dragonfly.

        Raises:
            NotAuthenticatedError: нет служебного токена или он не прошёл проверку — 401.
            ServiceScopeDeniedError: у сервиса нет `projects.acl.read` — 403.
            AccessUnavailableError: БД недоступна — 503.
        """
        try:
            await self._verifier.verify(authorization, ACL_SCOPE)
        except kit.NotAuthenticatedError as exc:
            raise NotAuthenticatedError({"reason": "service_token"}) from exc
        except kit.PermissionDeniedError as exc:
            raise ServiceScopeDeniedError({"scope": ACL_SCOPE}) from exc
        try:
            return await self._acl.fetch(project_id, user_id)
        except kit.DependencyUnavailableError as exc:
            raise AccessUnavailableError({"dependency": exc.dependency}) from exc
