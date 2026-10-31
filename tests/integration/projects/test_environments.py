import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db.enums import BuiltinRole
from tests.integration.conftest import SignIn
from tests.integration.projects.test_projects import create_project
from tests.support.members import add_member


@pytest.mark.case(id="ENV-001")
async def test_manager_creates_lists_and_updates_environments(
    client: AsyncClient, sign_in: SignIn
) -> None:
    owner = await sign_in()
    project = await create_project(client, owner.headers, "shop")
    base = f"/api/v1/projects/{project['id']}/environments"

    created = await client.post(
        base,
        json={"name": "Production", "slug": "prod", "is_production": True},
        headers=owner.headers,
    )
    updated = await client.patch(
        f"/api/v1/environments/{created.json()['id']}",
        json={"name": "Prod"},
        headers=owner.headers,
    )
    listed = await client.get(base, headers=owner.headers)

    assert created.status_code == 201
    assert updated.json()["name"] == "Prod"
    assert updated.json()["slug"] == "prod"
    assert updated.json()["is_production"] is True
    assert listed.json() == {"items": [updated.json()], "next_cursor": None}


@pytest.mark.case(id="ENV-002")
async def test_environment_slug_is_unique_in_project(client: AsyncClient, sign_in: SignIn) -> None:
    owner = await sign_in()
    project = await create_project(client, owner.headers, "shop")
    base = f"/api/v1/projects/{project['id']}/environments"
    await client.post(base, json={"name": "Stage", "slug": "stage"}, headers=owner.headers)

    response = await client.post(
        base, json={"name": "Stage 2", "slug": "stage"}, headers=owner.headers
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "environment.slug_taken"


@pytest.mark.case(id="ENV-003")
async def test_environment_rights_follow_project_membership(
    client: AsyncClient, sign_in: SignIn, db: AsyncSession
) -> None:
    owner, viewer, stranger = await sign_in(), await sign_in(), await sign_in()
    project = await create_project(client, owner.headers, "shop")
    await add_member(db, project["id"], viewer.user_id, BuiltinRole.VIEWER)
    base = f"/api/v1/projects/{project['id']}/environments"
    environment = (
        await client.post(base, json={"name": "Dev", "slug": "dev"}, headers=owner.headers)
    ).json()
    change = {"name": "Dev", "slug": "development"}

    viewer_create = await client.post(base, json=change, headers=viewer.headers)
    viewer_list = await client.get(base, headers=viewer.headers)
    stranger_update = await client.patch(
        f"/api/v1/environments/{environment['id']}", json=change, headers=stranger.headers
    )

    assert viewer_create.status_code == 403
    assert viewer_list.status_code == 200
    assert stranger_update.status_code == 404
    assert stranger_update.json()["error"]["code"] == "environment.not_found"
