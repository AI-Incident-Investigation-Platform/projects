from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid7

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db.enums import BuiltinRole
from src.core.db.models import Invitation
from tests.integration.conftest import Mailbox, SignIn
from tests.integration.projects.test_projects import create_project
from tests.support.members import add_member
from tests.support.users import UsersDirectory


async def invite(
    client: AsyncClient, headers: dict[str, str], project_id: str, user_id: UUID, role: str
) -> Response:
    return await client.post(
        f"/api/v1/projects/{project_id}/invitations",
        json={"user_id": str(user_id), "role": role},
        headers=headers,
    )


@pytest.mark.case(id="INVITE-001")
async def test_invited_user_gets_letter_and_joins_by_accepting(
    client: AsyncClient, sign_in: SignIn, mailbox: Mailbox, users: UsersDirectory
) -> None:
    owner, guest = await sign_in(), await sign_in()
    users.add(owner.user_id, "yuri", "Юрий")
    users.add(guest.user_id, "oleg")
    project = await create_project(client, owner.headers, "shop")

    created = await invite(client, owner.headers, project["id"], guest.user_id, "developer")
    letter = await mailbox.next_letter()
    inbox = await client.get("/api/v1/invitations", headers=guest.headers)
    invitation_id = created.json()["id"]
    accepted = await client.post(
        f"/api/v1/invitations/{invitation_id}/accept", headers=guest.headers
    )
    again = await client.post(f"/api/v1/invitations/{invitation_id}/accept", headers=guest.headers)
    visible = await client.get(f"/api/v1/projects/{project['id']}", headers=guest.headers)
    pending = await client.get(
        f"/api/v1/projects/{project['id']}/invitations", headers=owner.headers
    )

    assert created.status_code == 201
    assert created.json()["status"] == "pending"
    assert letter["template"] == "projects.invitation"
    assert letter["to"] == "oleg@example.com"
    assert letter["params"]["inviter_name"] == "Юрий"
    assert letter["params"]["project_name"] == "Shop"
    assert letter["params"]["role_name"] == "Разработчик"
    assert users.tokens and all(token.startswith("Bearer ") for token in users.tokens)
    assert [item["id"] for item in inbox.json()["items"]] == [invitation_id]
    assert inbox.json()["items"][0]["project"]["slug"] == "shop"
    assert accepted.status_code == again.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert visible.status_code == 200
    assert pending.json()["items"] == []


@pytest.mark.case(id="INVITE-002")
async def test_invitation_is_checked_before_it_is_sent(
    client: AsyncClient,
    sign_in: SignIn,
    db: AsyncSession,
    mailbox: Mailbox,
    users: UsersDirectory,
) -> None:
    owner = await sign_in()
    admin = await sign_in()
    developer = await sign_in()
    guest = await sign_in()
    for user, name in [(owner, "yuri"), (admin, "rasul"), (developer, "daniil"), (guest, "oleg")]:
        users.add(user.user_id, name)
    project = await create_project(client, owner.headers, "shop")
    await add_member(db, project["id"], admin.user_id, BuiltinRole.ADMIN)
    await add_member(db, project["id"], developer.user_id, BuiltinRole.DEVELOPER)
    pid = project["id"]

    first = await invite(client, owner.headers, pid, guest.user_id, "viewer")
    await mailbox.next_letter()
    duplicate = await invite(client, owner.headers, pid, guest.user_id, "viewer")
    member = await invite(client, owner.headers, pid, developer.user_id, "viewer")
    unknown_user = await invite(client, owner.headers, pid, uuid7(), "viewer")
    unknown_role = await invite(client, owner.headers, pid, guest.user_id, "boss")
    by_developer = await invite(client, developer.headers, pid, guest.user_id, "viewer")
    owner_by_admin = await invite(client, admin.headers, pid, guest.user_id, "owner")

    def code(response: Response) -> tuple[int, str]:
        return response.status_code, response.json()["error"]["code"]

    assert first.status_code == 201
    assert code(duplicate) == (409, "invitation.already_pending")
    assert code(member) == (409, "invitation.already_member")
    assert code(unknown_user) == (422, "invitation.user_invalid")
    assert code(unknown_role) == (422, "invitation.role_invalid")
    assert code(by_developer) == (403, "access.permission_denied")
    assert code(owner_by_admin) == (403, "access.role_not_grantable")
    assert await mailbox.is_empty()


@pytest.mark.case(id="INVITE-003")
async def test_answered_revoked_and_expired_invitations_are_final(
    client: AsyncClient,
    sign_in: SignIn,
    db: AsyncSession,
    mailbox: Mailbox,
    users: UsersDirectory,
) -> None:
    owner = await sign_in()
    guest = await sign_in()
    stranger = await sign_in()
    users.add(owner.user_id, "yuri")
    users.add(guest.user_id, "oleg")
    project = await create_project(client, owner.headers, "shop")
    pid = project["id"]

    declined_id = (await invite(client, owner.headers, pid, guest.user_id, "viewer")).json()["id"]
    foreign = await client.post(
        f"/api/v1/invitations/{declined_id}/accept", headers=stranger.headers
    )
    declined = await client.post(
        f"/api/v1/invitations/{declined_id}/decline", headers=guest.headers
    )
    declined_again = await client.post(
        f"/api/v1/invitations/{declined_id}/decline", headers=guest.headers
    )
    accept_declined = await client.post(
        f"/api/v1/invitations/{declined_id}/accept", headers=guest.headers
    )

    revoked_id = (await invite(client, owner.headers, pid, guest.user_id, "viewer")).json()["id"]
    revoked = await client.delete(
        f"/api/v1/projects/{pid}/invitations/{revoked_id}", headers=owner.headers
    )
    accept_revoked = await client.post(
        f"/api/v1/invitations/{revoked_id}/accept", headers=guest.headers
    )

    expired_id = (await invite(client, owner.headers, pid, guest.user_id, "viewer")).json()["id"]
    await db.execute(
        update(Invitation)
        .where(Invitation.id == UUID(expired_id))
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await db.commit()
    inbox = await client.get("/api/v1/invitations", headers=guest.headers)
    accept_expired = await client.post(
        f"/api/v1/invitations/{expired_id}/accept", headers=guest.headers
    )
    fresh = await invite(client, owner.headers, pid, guest.user_id, "viewer")

    assert foreign.status_code == 404
    assert declined.status_code == declined_again.status_code == 204
    assert accept_declined.status_code == 410
    assert revoked.status_code == 204
    assert accept_revoked.status_code == 410
    assert inbox.json()["items"] == []
    assert accept_expired.status_code == 410
    assert accept_expired.json()["error"]["code"] == "invitation.gone"
    assert fresh.status_code == 201


@pytest.mark.case(id="INVITE-004")
async def test_users_outage_blocks_invitation_but_lost_letter_does_not(
    client: AsyncClient, sign_in: SignIn, mailbox: Mailbox, users: UsersDirectory
) -> None:
    owner = await sign_in()
    guest = await sign_in()
    users.add(owner.user_id, "yuri")
    users.add(guest.user_id, "oleg")
    project = await create_project(client, owner.headers, "shop")

    users.available = False
    outage = await invite(client, owner.headers, project["id"], guest.user_id, "viewer")
    users.available = True
    await mailbox.detach()
    without_letter = await invite(client, owner.headers, project["id"], guest.user_id, "viewer")
    inbox = await client.get("/api/v1/invitations", headers=guest.headers)

    assert outage.status_code == 503
    assert outage.json()["error"]["code"] == "users.unavailable"
    assert without_letter.status_code == 201
    assert len(inbox.json()["items"]) == 1
