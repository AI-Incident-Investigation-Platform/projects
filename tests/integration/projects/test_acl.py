import json
from uuid import uuid7

import pytest
from aiip_kit.service_auth.fake import FakeServiceTokenProvider
from httpx import AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db.enums import BuiltinRole
from src.main import container
from tests.integration.conftest import SignIn
from tests.integration.projects.test_projects import create_project
from tests.support.members import add_member

ACL_URL = "/internal/v1/acl"


async def service_headers(scopes: list[str], audience: str = "projects") -> dict[str, str]:
    token = await FakeServiceTokenProvider("incidents").token(audience, scopes)
    return {"Authorization": f"Bearer {token}"}


async def get_acl(client: AsyncClient, project_id: object, user_id: object) -> Response:
    return await client.get(
        ACL_URL,
        params={"project_id": str(project_id), "user_id": str(user_id)},
        headers=await service_headers(["projects.acl.read"]),
    )


async def cached_member(project_id: object, user_id: object) -> dict:
    raw = await (await container.get(Redis)).hget(f"projects:members:{project_id}", str(user_id))
    assert raw is not None
    value: dict = json.loads(raw)
    return value


@pytest.mark.case(id="ACL-001")
async def test_acl_requires_service_token_with_scope(client: AsyncClient) -> None:
    params = {"project_id": str(uuid7()), "user_id": str(uuid7())}

    anonymous = await client.get(ACL_URL, params=params)
    wrong_scope = await client.get(
        ACL_URL, params=params, headers=await service_headers(["projects.tokens.read"])
    )
    foreign_audience = await client.get(
        ACL_URL, params=params, headers=await service_headers(["projects.acl.read"], "incidents")
    )

    assert anonymous.status_code == foreign_audience.status_code == 401
    assert anonymous.json()["error"]["code"] == "security.not_authenticated"
    assert wrong_scope.status_code == 403
    assert wrong_scope.json()["error"]["code"] == "security.scope_denied"


@pytest.mark.case(id="ACL-002")
async def test_acl_snapshot_for_member_stranger_and_missing_project(
    client: AsyncClient, sign_in: SignIn
) -> None:
    owner, stranger = await sign_in(), await sign_in()
    project = await create_project(client, owner.headers, "shop")

    member = await get_acl(client, project["id"], owner.user_id)
    foreign = await get_acl(client, project["id"], stranger.user_id)
    missing = await get_acl(client, uuid7(), owner.user_id)

    assert member.status_code == 200
    assert member.headers["cache-control"] == "no-store"
    body = member.json()
    assert body["project_state"] == "active"
    assert body["member"] == {"role_key": "owner", "version": body["acl_version"]}
    assert body["role"]["key"] == "owner"
    assert {"project.delete", "ownership.manage"} <= set(body["role"]["permissions"])
    assert body["fresh_until_ms"] - body["observed_at_ms"] == 5000
    assert (await cached_member(project["id"], owner.user_id))["role_key"] == "owner"
    roles = await (await container.get(Redis)).hget(f"projects:roles:{project['id']}", "owner")
    assert roles is not None
    assert foreign.status_code == 200
    assert foreign.json()["member"] is None
    assert foreign.json()["role"] is None
    assert (await cached_member(project["id"], stranger.user_id))["deleted"] is True
    assert missing.status_code == 200
    assert missing.json()["project_state"] == "missing"


@pytest.mark.case(id="ACL-003")
async def test_removed_member_loses_access_at_once(
    client: AsyncClient, sign_in: SignIn, db: AsyncSession
) -> None:
    owner, developer = await sign_in(), await sign_in()
    project = await create_project(client, owner.headers, "shop")
    base = f"/api/v1/projects/{project['id']}"
    await add_member(db, project["id"], developer.user_id, BuiltinRole.DEVELOPER)
    before = await client.get(base, headers=developer.headers)
    version_before = (await cached_member(project["id"], developer.user_id))["ver"]

    removed = await client.delete(f"{base}/members/{developer.user_id}", headers=owner.headers)
    after = await client.get(base, headers=developer.headers)

    assert before.status_code == 200
    assert removed.status_code == 204
    cached = await cached_member(project["id"], developer.user_id)
    assert cached["deleted"] is True
    assert cached["ver"] > version_before
    assert after.status_code == 404


@pytest.mark.case(id="ACL-004")
async def test_new_role_applies_at_once(
    client: AsyncClient, sign_in: SignIn, db: AsyncSession
) -> None:
    owner, admin = await sign_in(), await sign_in()
    project = await create_project(client, owner.headers, "shop")
    await add_member(db, project["id"], admin.user_id, BuiltinRole.ADMIN)
    environments = f"/api/v1/projects/{project['id']}/environments"
    created = await client.post(
        environments, json={"name": "Prod", "slug": "prod"}, headers=admin.headers
    )

    demoted = await client.patch(
        f"/api/v1/projects/{project['id']}/members/{admin.user_id}",
        json={"role": "viewer"},
        headers=owner.headers,
    )
    refused = await client.post(
        environments, json={"name": "Stage", "slug": "stage"}, headers=admin.headers
    )

    assert created.status_code == 201
    assert demoted.status_code == 200
    assert refused.status_code == 403
    assert (await cached_member(project["id"], admin.user_id))["role_key"] == "viewer"
