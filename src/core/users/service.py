import json
from collections.abc import Collection
from uuid import UUID

from src.core.users.client import UsersClient
from src.core.users.dto import UserProfile
from src.core.users.exc import UsersBadResponseError


class UsersService:
    def __init__(self, client: UsersClient) -> None:
        self._client = client

    async def get_profiles(
        self, access_token: str, user_ids: Collection[UUID]
    ) -> dict[UUID, UserProfile]:
        """Профили по id; кого нет в users, того нет и в ответе."""
        try:
            items = json.loads(await self._client.lookup(access_token, user_ids))["items"]
            profiles = [
                UserProfile(
                    id=UUID(item["id"]),
                    username=str(item["username"]),
                    display_name=item["display_name"],
                    email=str(item["email"]),
                )
                for item in items
            ]
        except (ValueError, KeyError, TypeError) as exc:
            raise UsersBadResponseError({"reason": "malformed_lookup"}) from exc
        return {profile.id: profile for profile in profiles}
