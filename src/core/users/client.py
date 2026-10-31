from collections.abc import Collection
from uuid import UUID

import httpx

from src.config import cfg
from src.core.users.exc import UsersBadResponseError, UsersUnavailableError


class UsersClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def lookup(self, access_token: str, user_ids: Collection[UUID]) -> bytes:
        """Профили по id от имени пользователя: его токен уходит в Authorization."""
        try:
            response = await self._http.get(
                f"{cfg.users.url}/api/v1/users/lookup",
                params=[("ids", str(user_id)) for user_id in user_ids],
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError as exc:
            raise UsersUnavailableError({"url": cfg.users.url}) from exc
        if response.is_server_error:
            raise UsersUnavailableError({"status": response.status_code})
        if response.status_code != httpx.codes.OK:
            raise UsersBadResponseError({"status": response.status_code})
        return response.content
