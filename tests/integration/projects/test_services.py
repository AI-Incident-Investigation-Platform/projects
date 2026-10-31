import pytest
from httpx import AsyncClient

from tests.integration.conftest import SignIn
from tests.integration.projects.test_projects import create_project


async def create_environment(
    client: AsyncClient, headers: dict[str, str], project_id: str, slug: str
) -> dict:
    response = await client.post(
        f"/api/v1/projects/{project_id}/environments",
        json={"name": slug, "slug": slug},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.case(id="SVC-001")
async def test_service_is_registered_filtered_and_updated(
    client: AsyncClient, sign_in: SignIn
) -> None:
    owner = await sign_in()
    project = await create_project(client, owner.headers, "shop")
    prod = await create_environment(client, owner.headers, project["id"], "prod")
    stage = await create_environment(client, owner.headers, project["id"], "stage")
    base = f"/api/v1/projects/{project['id']}/services"

    created = await client.post(
        base,
        json={
            "environment_id": prod["id"],
            "name": "payment-api",
            "external_names": ["payment-api", "payments"],
            "repository_url": "https://github.com/acme/payments",
        },
        headers=owner.headers,
    )
    await client.post(
        base, json={"environment_id": stage["id"], "name": "payment-api"}, headers=owner.headers
    )
    service_id = created.json()["id"]
    updated = await client.patch(
        f"/api/v1/services/{service_id}", json={"description": "API"}, headers=owner.headers
    )
    cleared = await client.patch(
        f"/api/v1/services/{service_id}", json={"repository_url": None}, headers=owner.headers
    )
    null_name = await client.patch(
        f"/api/v1/services/{service_id}", json={"name": None}, headers=owner.headers
    )
    in_prod = await client.get(f"{base}?environment_id={prod['id']}", headers=owner.headers)
    fetched = await client.get(f"/api/v1/services/{service_id}", headers=owner.headers)

    assert created.status_code == 201
    assert created.json()["external_names"] == ["payment-api", "payments"]
    assert updated.json()["description"] == "API"
    assert updated.json()["name"] == "payment-api"
    assert updated.json()["external_names"] == ["payment-api", "payments"]
    assert updated.json()["repository_url"] == "https://github.com/acme/payments"
    assert cleared.json()["repository_url"] is None
    assert cleared.json()["description"] == "API"
    assert null_name.status_code == 422
    assert [item["id"] for item in in_prod.json()["items"]] == [service_id]
    assert fetched.json() == cleared.json()


@pytest.mark.case(id="SVC-002")
async def test_service_cannot_use_environment_of_other_project(
    client: AsyncClient, sign_in: SignIn
) -> None:
    owner = await sign_in()
    mine = await create_project(client, owner.headers, "mine")
    other = await create_project(client, owner.headers, "other")
    foreign = await create_environment(client, owner.headers, other["id"], "prod")

    response = await client.post(
        f"/api/v1/projects/{mine['id']}/services",
        json={"environment_id": foreign["id"], "name": "api"},
        headers=owner.headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "service.environment_invalid"


@pytest.mark.case(id="SVC-003")
async def test_service_name_is_unique_in_environment_and_hidden_from_strangers(
    client: AsyncClient, sign_in: SignIn
) -> None:
    owner, stranger = await sign_in(), await sign_in()
    project = await create_project(client, owner.headers, "shop")
    prod = await create_environment(client, owner.headers, project["id"], "prod")
    base = f"/api/v1/projects/{project['id']}/services"
    body = {"environment_id": prod["id"], "name": "api"}
    service = (await client.post(base, json=body, headers=owner.headers)).json()

    duplicate = await client.post(base, json=body, headers=owner.headers)
    foreign_read = await client.get(f"/api/v1/services/{service['id']}", headers=stranger.headers)

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "service.name_taken"
    assert foreign_read.status_code == 404
    assert foreign_read.json()["error"]["code"] == "service.not_found"
