import hashlib
import logging
import secrets
from datetime import UTC, datetime
from uuid import UUID

from src.api.api_tokens.dto import ApiTokenInput, IssuedApiToken
from src.api.exc.api_tokens import (
    ApiTokenEnvironmentInvalidError,
    ApiTokenExpiryInvalidError,
    ApiTokenNotFoundError,
)
from src.core.access.service import ProjectAccess
from src.core.db.dto.api_token import ApiTokenDTO
from src.core.db.enums import Permission
from src.core.db.models.api_token import ApiToken
from src.core.db.pagination import Page
from src.core.db.uow import UnitOfWork
from src.core.security.dto import CurrentUser

log = logging.getLogger(__name__)


class ApiTokenService:
    def __init__(self, uow: UnitOfWork, access: ProjectAccess) -> None:
        self._uow = uow
        self._access = access

    async def list_tokens(
        self, current_user: CurrentUser, project_id: UUID, cursor: str | None, limit: int
    ) -> Page[ApiTokenDTO]:
        await self._access.require(project_id, current_user, Permission.API_TOKEN_MANAGE)
        rows = await self._uow.api_tokens.list_for_project(
            project_id, Page.decode_cursor(cursor), limit + 1
        )
        return Page.from_rows(rows, limit, ApiTokenDTO.from_orm)

    async def issue_token(
        self, current_user: CurrentUser, project_id: UUID, data: ApiTokenInput
    ) -> IssuedApiToken:
        await self._access.require(project_id, current_user, Permission.API_TOKEN_MANAGE)
        if data.expires_at is not None and data.expires_at <= datetime.now(UTC):
            raise ApiTokenExpiryInvalidError({"project_id": str(project_id)})
        if data.environment_id is not None:
            environment = await self._uow.environments.get_by_id(data.environment_id)
            if environment is None or environment.project_id != project_id:
                raise ApiTokenEnvironmentInvalidError(
                    {"project_id": str(project_id), "environment_id": str(data.environment_id)},
                    {"environment_id": str(data.environment_id)},
                )
        secret = self._new_secret()
        token = ApiToken(
            project_id=project_id,
            environment_id=data.environment_id,
            name=data.name,
            prefix=secret[:12],
            token_hash=self.hash_secret(secret),
            scopes=sorted(data.scopes),
            created_by=current_user.user_id,
            expires_at=data.expires_at,
        )
        self._uow.api_tokens.add(token)
        await self._uow.commit()
        log.info(
            "Выпущен API-токен проекта",
            extra={
                "event": "api_token.issued",
                "project_id": str(project_id),
                "token_id": str(token.id),
            },
        )
        return IssuedApiToken(token=ApiTokenDTO.from_orm(token), secret=secret)

    async def revoke_token(
        self, current_user: CurrentUser, project_id: UUID, token_id: UUID
    ) -> None:
        """Отзывает токен; повторный отзыв ничего не меняет. Строка остаётся для истории."""
        await self._access.require(project_id, current_user, Permission.API_TOKEN_MANAGE)
        token = await self._uow.api_tokens.get_in_project(project_id, token_id)
        if token is None:
            raise ApiTokenNotFoundError({"token_id": str(token_id)})
        if token.revoked_at is not None:
            return
        token.revoked_at = datetime.now(UTC)
        await self._uow.commit()
        log.info(
            "API-токен проекта отозван",
            extra={
                "event": "api_token.revoked",
                "project_id": str(project_id),
                "token_id": str(token_id),
            },
        )

    @staticmethod
    def hash_secret(secret: str) -> str:
        # у случайного 256-битного токена перебор невозможен, медленный хэш не нужен
        return hashlib.sha256(secret.encode()).hexdigest()

    @staticmethod
    def _new_secret() -> str:
        return f"aiip_{secrets.token_urlsafe(32)}"
