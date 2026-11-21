from aiip_kit.access.checker import AccessChecker, DragonflyAccessChecker
from aiip_kit.service_auth.verifier import JwtServiceTokenVerifier, ServiceTokenVerifier
from dishka import Provider, Scope, provide
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.config import cfg
from src.core.access.acl import AclStore
from src.core.security.signing_keys import SigningKeys


class AccessProvider(Provider):
    @provide(scope=Scope.APP)
    def get_acl_store(self, session_factory: async_sessionmaker, redis: Redis) -> AclStore:
        return AclStore(session_factory, redis)

    @provide(scope=Scope.APP)
    def get_access_checker(self, redis: Redis, acl: AclStore) -> AccessChecker:
        # промах кэша projects читает из своей БД, а не зовёт себя по HTTP
        return DragonflyAccessChecker(redis, acl, session_prefix=cfg.auth.session_key_prefix)

    @provide(scope=Scope.APP)
    def get_service_token_verifier(self, signing_keys: SigningKeys) -> ServiceTokenVerifier:
        # служебный токен auth подписан тем же ключом, что и пользовательский: JWKS общий
        return JwtServiceTokenVerifier(
            signing_keys, audience=cfg.service.name, issuer=cfg.auth.issuer
        )
