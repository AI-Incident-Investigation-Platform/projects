from pathlib import Path
from urllib.parse import quote

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

BASE_DIR = Path(__file__).parent.parent.parent
TOML_SETTINGS_PATH = BASE_DIR / "config.toml"

PATHS_SOURCES: list[tuple[Path, type[PydanticBaseSettingsSource]]] = [
    (TOML_SETTINGS_PATH, TomlConfigSettingsSource),
]


class Service(BaseModel):
    name: str = "projects"
    # тег образа, его подставляет сборка; на хосте — dev
    version: str = "dev"
    port: int = 8003
    bind_host: str = "127.0.0.1"
    # предел замерен на auth (закон Литтла); для projects не перемерялся
    max_concurrent_requests: int = Field(default=64, ge=1)
    overload_retry_after_seconds: int = Field(default=2, ge=1)


class Database(BaseModel):
    postgres_username: str = ""
    postgres_db: str = ""
    postgres_port: int = 5432
    postgres_host: str = ""
    postgres_password: str = ""
    # постоянный пул без overflow: соединения сверх пула открывались и закрывались на каждом пике
    pool_size: int = Field(default=10, ge=1)
    pool_max_overflow: int = Field(default=0, ge=0)
    pool_timeout_seconds: float = Field(default=2, gt=0)
    pool_recycle_seconds: int = Field(default=1800, ge=1)
    statement_timeout_ms: int = Field(default=5000, ge=1)
    lock_timeout_ms: int = Field(default=2000, ge=1)

    @property
    def async_database_url(self) -> str:
        user = quote(self.postgres_username, safe="")
        password = quote(self.postgres_password, safe="")
        return f"postgresql+asyncpg://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


class Cache(BaseModel):
    host: str = ""
    port: int = 6379
    password: str = ""
    db: int = 0
    key_prefix: str = "projects:"
    timeout_seconds: float = 2

    @property
    def url(self) -> str:
        credentials = f"default:{quote(self.password, safe='')}@" if self.password else ""
        return f"redis://{credentials}{self.host}:{self.port}/{self.db}"


class Tracing(BaseModel):
    enabled: bool = True
    otlp_endpoint: str = ""


class Auth(BaseModel):
    jwks_url: str = ""
    issuer: str = "auth"
    audience: str = "aiip"
    jwks_timeout_seconds: float = Field(default=2, gt=0)
    # неизвестный kid перечитывает JWKS не чаще раза в этот интервал: чужой токен не заваливает auth
    jwks_refresh_interval_seconds: int = Field(default=30, ge=1)
    # пропуск живой сессии ведёт auth в своём префиксе кэша
    session_key_prefix: str = "auth:session:"
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost", "https://localhost"]
    )


class Users(BaseModel):
    url: str = "http://users.apps:8004"
    timeout_seconds: float = Field(default=2, gt=0)


class Rabbitmq(BaseModel):
    url: str = ""
    connect_timeout_seconds: float = Field(default=2, gt=0)
    publish_timeout_seconds: float = Field(default=2, gt=0)


class Email(BaseModel):
    exchange: str = "email"
    transactional_routing_key: str = "send.transactional"
    locale: str = "ru"


class Invitations(BaseModel):
    ttl_days: int = Field(default=7, ge=1)
    # страница фронтенда со входящими приглашениями; ссылка из письма ведёт на неё
    accept_url: str = "http://localhost/invitations"
    # письмо, не отправленное за сутки, уже не нужно: приглашение видно в интерфейсе
    letter_ttl_seconds: int = Field(default=86400, ge=1)


class Pagination(BaseModel):
    default_limit: int = Field(default=50, ge=1)
    max_limit: int = Field(default=200, ge=1)


class Logging(BaseModel):
    level: str = "INFO"
    slow_request_ms: int = 1000


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        toml_file=TOML_SETTINGS_PATH,
        env_nested_delimiter="__",
    )

    service: Service = Service()
    database: Database = Database()
    cache: Cache = Cache()
    tracing: Tracing = Tracing()
    auth: Auth = Auth()
    users: Users = Users()
    rabbitmq: Rabbitmq = Rabbitmq()
    email: Email = Email()
    invitations: Invitations = Invitations()
    pagination: Pagination = Pagination()
    logging: Logging = Logging()

    def missing_required(self) -> list[str]:
        required = {
            "database.postgres_host": self.database.postgres_host,
            "database.postgres_db": self.database.postgres_db,
            "database.postgres_username": self.database.postgres_username,
            "cache.host": self.cache.host,
            "auth.jwks_url": self.auth.jwks_url,
            "rabbitmq.url": self.rabbitmq.url,
        }
        if self.tracing.enabled:
            required["tracing.otlp_endpoint"] = self.tracing.otlp_endpoint
        return [name for name, value in required.items() if not value]

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        active_sources = [method(settings_cls) for path, method in PATHS_SOURCES if path.exists()]
        return EnvSettingsSource(settings_cls), *active_sources


cfg = Config()
