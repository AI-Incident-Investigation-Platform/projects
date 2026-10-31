import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db.enums import BuiltinRole
from tests.integration.conftest import SignIn
from tests.support.members import add_member


async def create_project(client: AsyncClient, headers: dict[str, str], slug: str) -> dict:
    response = await client.post(
        "/api/v1/projects", json={"name": slug.title(), "slug": slug}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.case(id="PROJ-001")
async def test_creator_becomes_owner_and_sees_project(client: AsyncClient, sign_in: SignIn) -> None:
    owner = await sign_in()

    project = await create_project(client, owner.headers, "payments")
    updated = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"name": "Payments", "slug": "payments-core", "description": "Платежи"},
        headers=owner.headers,
    )
    renamed = await client.patch(
        f"/api/v1/projects/{project['id']}", json={"name": "Платежи"}, headers=owner.headers
    )
    listed = await client.get("/api/v1/projects", headers=owner.headers)

    assert renamed.json()["slug"] == "payments-core"
    assert renamed.json()["description"] == "Платежи"
    assert renamed.json()["name"] == "Платежи"
    assert project["archived_at"] is None
    assert project["created_at"].endswith("Z")
    assert updated.status_code == 200
    assert updated.json()["slug"] == "payments-core"
    assert [item["id"] for item in listed.json()["items"]] == [project["id"]]


@pytest.mark.case(id="PROJ-002")
async def test_list_shows_only_own_projects_page_by_page(
    client: AsyncClient, sign_in: SignIn
) -> None:
    alice, bob = await sign_in(), await sign_in()
    first = await create_project(client, alice.headers, "alpha")
    second = await create_project(client, alice.headers, "beta")
    await create_project(client, bob.headers, "gamma")

    page_one = (await client.get("/api/v1/projects?limit=1", headers=alice.headers)).json()
    page_two = (
        await client.get(
            f"/api/v1/projects?limit=1&cursor={page_one['next_cursor']}", headers=alice.headers
        )
    ).json()

    assert [item["id"] for item in page_one["items"]] == [first["id"]]
    assert [item["id"] for item in page_two["items"]] == [second["id"]]
    assert page_two["next_cursor"] is None


@pytest.mark.case(id="PROJ-003")
async def test_foreign_project_is_not_found(client: AsyncClient, sign_in: SignIn) -> None:
    owner, stranger = await sign_in(), await sign_in()
    project = await create_project(client, owner.headers, "secret")

    read = await client.get(f"/api/v1/projects/{project['id']}", headers=stranger.headers)
    write = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"name": "Mine", "slug": "mine"},
        headers=stranger.headers,
    )

    assert read.status_code == write.status_code == 404
    assert read.json()["error"]["code"] == "project.not_found"


@pytest.mark.case(id="PROJ-004")
async def test_member_without_right_is_forbidden(
    client: AsyncClient, sign_in: SignIn, db: AsyncSession
) -> None:
    owner, viewer = await sign_in(), await sign_in()
    project = await create_project(client, owner.headers, "shared")
    await add_member(db, project["id"], viewer.user_id, BuiltinRole.VIEWER)

    read = await client.get(f"/api/v1/projects/{project['id']}", headers=viewer.headers)
    write = await client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"name": "Shared", "slug": "renamed"},
        headers=viewer.headers,
    )

    assert read.status_code == 200
    assert write.status_code == 403
    assert write.json()["error"]["code"] == "access.permission_denied"
    assert write.json()["error"]["details"] == {"permission": "project.manage"}


@pytest.mark.case(id="PROJ-005")
async def test_taken_slug_is_conflict(client: AsyncClient, sign_in: SignIn) -> None:
    first, second = await sign_in(), await sign_in()
    await create_project(client, first.headers, "taken")

    response = await client.post(
        "/api/v1/projects", json={"name": "Taken", "slug": "taken"}, headers=second.headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "project.slug_taken"


@pytest.mark.case(id="PROJ-006")
async def test_anonymous_and_cross_site_requests_are_rejected(
    client: AsyncClient, sign_in: SignIn
) -> None:
    user = await sign_in()

    anonymous = await client.get("/api/v1/projects")
    cross_site = await client.post(
        "/api/v1/projects",
        json={"name": "X", "slug": "xx"},
        headers={**user.headers, "Origin": "https://evil.example"},
    )

    assert anonymous.status_code == 401
    assert cross_site.status_code == 403
    assert cross_site.json()["error"]["code"] == "security.origin_forbidden"


@pytest.mark.case(id="PROJ-007")
async def test_malformed_cursor_is_rejected(client: AsyncClient, sign_in: SignIn) -> None:
    user = await sign_in()

    response = await client.get("/api/v1/projects?cursor=@@@", headers=user.headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request.invalid_cursor"
