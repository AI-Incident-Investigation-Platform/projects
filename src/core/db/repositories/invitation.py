from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import joinedload

from src.core.db.enums import InvitationStatus
from src.core.db.models.invitation import Invitation
from src.core.db.repositories.base import BaseRepository


class InvitationRepository(BaseRepository[Invitation]):
    model = Invitation

    async def get_for_update(self, invitation_id: UUID) -> Invitation | None:
        query = (
            self._with_details()
            .where(Invitation.id == invitation_id)
            .with_for_update(of=Invitation)
        )
        return await self._session.scalar(query)

    async def get_in_project_for_update(
        self, project_id: UUID, invitation_id: UUID
    ) -> Invitation | None:
        query = (
            self._with_details()
            .where(Invitation.project_id == project_id, Invitation.id == invitation_id)
            .with_for_update(of=Invitation)
        )
        return await self._session.scalar(query)

    async def get_pending_for_update(self, project_id: UUID, user_id: UUID) -> Invitation | None:
        query = (
            select(Invitation)
            .where(
                Invitation.project_id == project_id,
                Invitation.user_id == user_id,
                Invitation.status == InvitationStatus.PENDING,
            )
            .with_for_update()
        )
        return await self._session.scalar(query)

    async def list_pending_for_project(
        self, project_id: UUID, now: datetime
    ) -> Sequence[Invitation]:
        query = (
            self._with_details()
            .where(
                Invitation.project_id == project_id,
                Invitation.status == InvitationStatus.PENDING,
                Invitation.expires_at > now,
            )
            .order_by(Invitation.id)
        )
        return (await self._session.scalars(query)).all()

    async def list_pending_for_user(self, user_id: UUID, now: datetime) -> Sequence[Invitation]:
        query = (
            self._with_details()
            .where(
                Invitation.user_id == user_id,
                Invitation.status == InvitationStatus.PENDING,
                Invitation.expires_at > now,
            )
            .order_by(Invitation.id)
        )
        return (await self._session.scalars(query)).all()

    @staticmethod
    def _with_details() -> Select[tuple[Invitation]]:
        return select(Invitation).options(
            joinedload(Invitation.project), joinedload(Invitation.role)
        )
