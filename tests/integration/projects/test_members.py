import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db.enums import BuiltinRole
from tests.integration.conftest import SignIn
from tests.integration.projects.test_projects import create_project
from tests.support.members import add_member


@pytest.mark.case(id="MEMBER-001")
async def test_roles_are_changed_only_within_own_permissions(
    client: AsyncClient, sign_in: SignIn, db: AsyncSession
) -> None:
    owner, admin, developer = await sign_in(), await sign_in(), await sign_in()
    project = await create_project(client, owner.headers, "shop")
    base = f"/api/v1/projects/{project['id']}"
    await add_member(db, project["id"], admin.user_id, BuiltinRole.ADMIN)
    await add_member(db, project["id"], developer.user_id, BuiltinRole.DEVELOPER)

    roles = await client.get(f"{base}/roles", headers=developer.headers)
    members = await client.get(f"{base}/members", headers=developer.headers)
    by_developer = await client.patch(
        f"{base}/members/{admin.user_id}", json={"role": "viewer"}, headers=developer.headers
    )
    own = await client.patch(
        f"{base}/members/{admin.user_id}", json={"role": "viewer"}, headers=admin.headers
    )
    admin_on_owner = await client.patch(
        f"{base}/members/{owner.user_id}", json={"role": "viewer"}, headers=admin.headers
    )
    admin_grants_owner = await client.patch(
        f"{base}/members/{developer.user_id}", json={"role": "owner"}, headers=admin.headers
    )
    unknown = await client.patch(
        f"{base}/members/{developer.user_id}", json={"role": "boss"}, headers=admin.headers
    )
    demoted = await client.patch(
        f"{base}/members/{developer.user_id}", json={"role": "viewer"}, headers=admin.headers
    )

    assert [role["key"] for role in roles.json()["items"]] == [
        "owner",
        "admin",
        "developer",
        "viewer",
    ]
    assert {m["user_id"]: m["role"]["key"] for m in members.json()["items"]} == {
        str(owner.user_id): "owner",
        str(admin.user_id): "admin",
        str(developer.user_id): "developer",
    }
    assert by_developer.status_code == 403
    assert by_developer.json()["error"]["code"] == "access.permission_denied"
    assert own.status_code == 422
    assert own.json()["error"]["code"] == "member.own_role"
    assert admin_on_owner.status_code == admin_grants_owner.status_code == 403
    assert admin_on_owner.json()["error"]["code"] == "access.role_not_grantable"
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "member.role_invalid"
    assert demoted.status_code == 200
    assert demoted.json()["role"]["key"] == "viewer"


@pytest.mark.case(id="MEMBER-002")
async def test_last_owner_stays_and_members_can_leave(
    client: AsyncClient, sign_in: SignIn, db: AsyncSession
) -> None:
    owner, second, developer = await sign_in(), await sign_in(), await sign_in()
    project = await create_project(client, owner.headers, "shop")
    base = f"/api/v1/projects/{project['id']}/members"
    await add_member(db, project["id"], developer.user_id, BuiltinRole.DEVELOPER)

    alone = await client.delete(f"{base}/{owner.user_id}", headers=owner.headers)
    left = await client.delete(f"{base}/{developer.user_id}", headers=developer.headers)
    await add_member(db, project["id"], second.user_id, BuiltinRole.OWNER)
    demoted = await client.patch(
        f"{base}/{owner.user_id}", json={"role": "admin"}, headers=second.headers
    )
    last = await client.patch(
        f"{base}/{second.user_id}", json={"role": "admin"}, headers=owner.headers
    )
    gone = await client.get(f"/api/v1/projects/{project['id']}", headers=developer.headers)

    assert alone.status_code == 422
    assert alone.json()["error"]["code"] == "member.last_owner"
    assert left.status_code == 204
    assert gone.status_code == 404
    assert demoted.status_code == 200
    assert last.status_code == 403
