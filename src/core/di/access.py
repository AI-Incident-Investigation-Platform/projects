from aiip_kit.access.checker import AccessChecker, DragonflyAccessChecker
from aiip_kit.service_auth.fake import FakeServiceTokenVerifier
from aiip_kit.service_auth.verifier import ServiceTokenVerifier
from dishka import Provider, Scope, provide
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.config import cfg
from src.core.access.acl import AclStore


class AccessProvider(Provider):
    @provide(scope=Scope.APP)
    def get_acl_store(self, session_factory: async_sessionmaker, redis: Redis) -> AclStore:
        return AclStore(session_factory, redis)

    @provide(scope=Scope.APP)
    def get_access_checker(self, redis: Redis, acl: AclStore) -> AccessChecker:
        # промах кэша projects читает из своей БД, а не зовёт себя по HTTP
        return DragonflyAccessChecker(redis, acl, session_prefix=cfg.auth.session_key_prefix)

    @provide(scope=Scope.APP)
    def get_service_token_verifier(self) -> ServiceTokenVerifier:
        # до выдачи служебных токенов в auth (AUTH-4) — fake из aiip-kit; internal API
        # не опубликован через Traefik и доступен только изнутри кластера
        return FakeServiceTokenVerifier(cfg.service.name)
