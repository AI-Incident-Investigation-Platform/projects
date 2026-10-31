from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, provide

from src.config import cfg
from src.core.users.client import UsersClient
from src.core.users.service import UsersService


class UsersProvider(Provider):
    users_service = provide(UsersService, scope=Scope.APP)

    @provide(scope=Scope.APP)
    async def get_client(self) -> AsyncIterator[UsersClient]:
        # Service балансирует соединения: короткий keep-alive даёт трафик новым подам users
        async with httpx.AsyncClient(
            timeout=cfg.users.timeout_seconds, limits=httpx.Limits(keepalive_expiry=30)
        ) as http:
            yield UsersClient(http)
