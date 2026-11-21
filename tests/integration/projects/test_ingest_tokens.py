import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import aio_pika
import pytest
from aiip_kit.api_tokens.reader import ApiTokenInfo
from aiip_kit.messaging.amqp import to_amqp
from aiip_kit.messaging.message import MessageV1
from httpx import AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import cfg
from src.core.db.models import ApiToken
from src.main import container
from src.worker.token_usage.consumer import TOKEN_USED, TokenUsageConsumer
from tests.integration.conftest import SignIn
from tests.integration.projects.test_projects import create_project
from tests.support.tokens import issue_service_token


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


async def lookup(client: AsyncClient, token_hash: str, scopes: list[str] | None = None) -> Response:
    token = issue_service_token("ingest", "projects", scopes or ["projects.tokens.read"])
    return await client.get(
        f"/internal/v1/api-tokens/{token_hash}", headers={"Authorization": f"Bearer {token}"}
    )


async def cached(token_hash: str) -> dict:
    raw = await (await container.get(Redis)).get(f"projects:token:{token_hash}")
    assert raw is not None
    value: dict = json.loads(raw)
    return value


async def issue(client: AsyncClient, sign_in: SignIn) -> tuple[dict, dict, dict[str, str]]:
    owner = await sign_in()
    project = await create_project(client, owner.headers, "shop")
    issued = await client.post(
        f"/api/v1/projects/{project['id']}/api-tokens",
        json={"name": "Alertmanager"},
        headers=owner.headers,
    )
    assert issued.status_code == 201
    return project, issued.json(), owner.headers


@pytest.mark.case(id="INGEST-TOKEN-001")
async def test_lookup_requires_scope_and_caches_unknown_digest(client: AsyncClient) -> None:
    unknown = "0" * 64

    wrong_scope = await lookup(client, unknown, ["projects.acl.read"])
    anonymous = await client.get(f"/internal/v1/api-tokens/{unknown}")
    malformed = await lookup(client, "not-a-digest")
    missing = await lookup(client, unknown)

    assert wrong_scope.status_code == 403
    assert anonymous.status_code == 401
    assert malformed.status_code == 422
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "api_token.unknown"
    negative = await cached(unknown)
    assert negative["state"] == "unknown"
    assert negative["fresh_until_ms"] - negative["observed_at_ms"] == 1000


@pytest.mark.case(id="INGEST-TOKEN-002")
async def test_issue_and_revoke_rewrite_cache_at_once(
    client: AsyncClient, sign_in: SignIn, db: AsyncSession
) -> None:
    project, body, headers = await issue(client, sign_in)
    token_hash = digest(body["secret"])
    after_issue = await cached(token_hash)

    found = await lookup(client, token_hash)
    revoked = await client.delete(
        f"/api/v1/projects/{project['id']}/api-tokens/{body['token']['id']}", headers=headers
    )
    after_revoke = await cached(token_hash)
    await db.execute(
        update(ApiToken)
        .where(ApiToken.id == UUID(body["token"]["id"]))
        .values(revoked_at=None, expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await db.commit()
    expired = await lookup(client, token_hash)

    assert after_issue["state"] == "active"
    assert after_issue["ver"] == 1
    assert found.status_code == 200
    assert found.headers["cache-control"] == "no-store"
    info = ApiTokenInfo.from_json(found.json())
    assert info.project_id == UUID(project["id"])
    assert info.allows("alert.ingest", datetime.now(UTC))
    assert revoked.status_code == 204
    assert after_revoke["state"] == "revoked"
    assert after_revoke["ver"] == 2
    assert expired.json()["state"] == "expired"
    # в кэше остаётся отзыв: версия 2 старше снимка истёкшего токена
    assert (await cached(token_hash))["state"] == "revoked"


@pytest.mark.case(id="INGEST-TOKEN-003")
async def test_token_used_moves_last_used_at_forward_only(
    client: AsyncClient, sign_in: SignIn, db: AsyncSession
) -> None:
    _, body, _ = await issue(client, sign_in)
    token_id = body["token"]["id"]
    connection = await aio_pika.connect(cfg.rabbitmq.url)
    channel = await connection.channel(publisher_confirms=True)
    await TokenUsageConsumer(container).start(channel)
    exchange = await channel.get_exchange(f"{cfg.service.name}.commands")
    later = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
    earlier = later - timedelta(hours=1)

    async def send(used_at: datetime) -> None:
        message = MessageV1(
            kind="command",
            type=TOKEN_USED,
            producer="ingest",
            data={"items": [{"token_id": token_id, "last_used_at": used_at.isoformat()}]},
        )
        await exchange.publish(to_amqp(message), routing_key=TOKEN_USED)

    async def last_used() -> datetime | None:
        db.expire_all()
        return await db.scalar(select(ApiToken.last_used_at).where(ApiToken.id == UUID(token_id)))

    async def wait_for(expected: datetime) -> None:
        for _ in range(100):
            if await last_used() == expected:
                return
            await asyncio.sleep(0.05)
        raise AssertionError(f"last_used_at != {expected}: {await last_used()}")

    try:
        await send(later)
        await wait_for(later)
        await send(earlier)
        await send(later)
        await asyncio.sleep(0.3)
        assert await last_used() == later
    finally:
        await connection.close()
