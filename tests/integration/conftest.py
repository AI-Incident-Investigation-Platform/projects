import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid7

import aio_pika
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import cfg
from src.core.db.db import engine, session_maker
from src.core.db.models import Base
from src.main import app as projects_app
from src.main import container
from tests.support.tokens import issue_access_token
from tests.support.users import DIRECTORY, UsersDirectory

ORIGIN = "http://testserver"


@dataclass(frozen=True)
class SignedInUser:
    user_id: UUID
    session_id: UUID
    headers: dict[str, str]


type SignIn = Callable[[], Awaitable[SignedInUser]]


@pytest.fixture(scope="session")
async def app() -> AsyncIterator[FastAPI]:
    yield projects_app
    await container.close()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver", headers={"Origin": ORIGIN}
    ) as c:
        yield c


@pytest.fixture
async def sign_in(app: FastAPI) -> SignIn:
    """Пользователь с живой сессией, как после входа в auth: токен в куке и пропуск в кэше."""
    cache = await container.get(Redis)

    async def make() -> SignedInUser:
        user_id, session_id = uuid7(), uuid7()
        await cache.set(f"{cfg.auth.session_key_prefix}{session_id}", 1, ex=900)
        token = issue_access_token(user_id, session_id)
        return SignedInUser(user_id, session_id, {"Cookie": f"access_token={token}"})

    return make


class Mailbox:
    """Очередь теста на месте сервиса email: забирает задачи на письма."""

    def __init__(
        self, connection: aio_pika.abc.AbstractConnection, queue: aio_pika.abc.AbstractQueue
    ) -> None:
        self._connection = connection
        self._queue = queue

    async def next_letter(self, timeout: float = 5) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            message = await self._queue.get(no_ack=True, fail=False)
            if message is not None:
                body: dict[str, Any] = json.loads(message.body)
                return body
            if asyncio.get_running_loop().time() > deadline:
                raise TimeoutError("projects не поставил письмо в очередь")
            await asyncio.sleep(0.05)

    async def is_empty(self) -> bool:
        return await self._queue.get(no_ack=True, fail=False) is None

    async def detach(self) -> None:
        await self._queue.delete(if_unused=False, if_empty=False)

    async def close(self) -> None:
        await self._connection.close()


@pytest.fixture
async def mailbox(app: FastAPI) -> AsyncIterator[Mailbox]:
    connection = await aio_pika.connect(cfg.rabbitmq.url)
    channel = await connection.channel()
    exchange = await channel.declare_exchange(
        cfg.email.exchange, aio_pika.ExchangeType.DIRECT, durable=True
    )
    queue = await channel.declare_queue(exclusive=True)
    await queue.bind(exchange, routing_key=cfg.email.transactional_routing_key)
    box = Mailbox(connection, queue)
    yield box
    await box.close()


@pytest.fixture
def users() -> Iterator[UsersDirectory]:
    yield DIRECTORY
    DIRECTORY.reset()


@pytest.fixture
async def db(app: FastAPI) -> AsyncIterator[AsyncSession]:
    async with session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture(autouse=True)
async def clean_state(app: FastAPI) -> AsyncIterator[None]:
    yield
    # встроенные роли заводит миграция, их тесты не трогают
    tables = ", ".join(
        f'"{table.name}"' for table in Base.metadata.sorted_tables if table.name != "roles"
    )
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} CASCADE"))
    await (await container.get(Redis)).flushdb()
