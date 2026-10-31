import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db.enums import BuiltinRole
from src.core.db.models import ApiToken
from tests.integration.conftest import SignIn
from tests.integration.projects.test_projects import create_project
from tests.integration.projects.test_services import create_environment
from tests.support.members import add_member


@pytest.mark.case(id="TOKEN-001")
async def test_secret_is_shown_once_and_stored_as_hash(
    client: AsyncClient, sign_in: SignIn, db: AsyncSession
) -> None:
    owner = await sign_in()
    project = await create_project(client, owner.headers, "shop")
    base = f"/api/v1/projects/{project['id']}/api-tokens"

    issued = await client.post(base, json={"name": "Alertmanager"}, headers=owner.headers)
    listed = await client.get(base, headers=owner.headers)

    body = issued.json()
    secret = body["secret"]
    stored = await db.scalar(select(ApiToken.token_hash).where(ApiToken.id == body["token"]["id"]))
    assert issued.status_code == 201
    assert issued.headers["cache-control"] == "no-store"
    assert secret.startswith("aiip_") and secret.startswith(body["token"]["prefix"])
    assert body["token"]["scopes"] == ["alert.ingest", "deployment.ingest"]
    assert stored == hashlib.sha256(secret.encode()).hexdigest()
    assert listed.json()["items"] == [body["token"]]
    assert secret not in listed.text


@pytest.mark.case(id="TOKEN-002")
async def test_revoked_token_stays_listed_and_revoke_is_idempotent(
    client: AsyncClient, sign_in: SignIn
) -> None:
    owner = await sign_in()
    project = await create_project(client, owner.headers, "shop")
    base = f"/api/v1/projects/{project['id']}/api-tokens"
    token = (await client.post(base, json={"name": "CI"}, headers=owner.headers)).json()["token"]

    first = await client.delete(f"{base}/{token['id']}", headers=owner.headers)
    second = await client.delete(f"{base}/{token['id']}", headers=owner.headers)
    listed = (await client.get(base, headers=owner.headers)).json()["items"]

    assert first.status_code == second.status_code == 204
    assert listed[0]["revoked_at"] is not None


@pytest.mark.case(id="TOKEN-003")
async def test_tokens_need_api_token_manage(
    client: AsyncClient, sign_in: SignIn, db: AsyncSession
) -> None:
    owner, developer, stranger = await sign_in(), await sign_in(), await sign_in()
    project = await create_project(client, owner.headers, "shop")
    await add_member(db, project["id"], developer.user_id, BuiltinRole.DEVELOPER)
    base = f"/api/v1/projects/{project['id']}/api-tokens"
    token = (await client.post(base, json={"name": "CI"}, headers=owner.headers)).json()["token"]

    developer_list = await client.get(base, headers=developer.headers)
    developer_issue = await client.post(base, json={"name": "x"}, headers=developer.headers)
    stranger_revoke = await client.delete(f"{base}/{token['id']}", headers=stranger.headers)
    missing = await client.delete(f"{base}/{project['id']}", headers=owner.headers)

    assert developer_list.status_code == developer_issue.status_code == 403
    assert stranger_revoke.status_code == 404
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "api_token.not_found"


@pytest.mark.case(id="TOKEN-004")
async def test_token_environment_and_expiry_are_validated(
    client: AsyncClient, sign_in: SignIn
) -> None:
    owner = await sign_in()
    project = await create_project(client, owner.headers, "shop")
    other = await create_project(client, owner.headers, "other")
    prod = await create_environment(client, owner.headers, project["id"], "prod")
    foreign = await create_environment(client, owner.headers, other["id"], "prod")
    base = f"/api/v1/projects/{project['id']}/api-tokens"
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()

    bound = await client.post(
        base,
        json={"name": "prod", "environment_id": prod["id"], "scopes": ["alert.ingest"]},
        headers=owner.headers,
    )
    wrong_env = await client.post(
        base, json={"name": "x", "environment_id": foreign["id"]}, headers=owner.headers
    )
    expired = await client.post(base, json={"name": "x", "expires_at": past}, headers=owner.headers)

    assert bound.status_code == 201
    assert bound.json()["token"]["environment_id"] == prod["id"]
    assert wrong_env.json()["error"]["code"] == "api_token.environment_invalid"
    assert expired.json()["error"]["code"] == "api_token.expiry_invalid"
