import logging
from uuid import UUID

from src.api.exc.members import (
    LastOwnerError,
    MemberNotFoundError,
    OwnRoleChangeError,
    RoleInvalidError,
)
from src.core.access.service import ProjectAccess
from src.core.db.dto.member import MemberDTO
from src.core.db.dto.role import RoleDTO
from src.core.db.enums import Permission
from src.core.db.models.membership import Membership
from src.core.db.uow import UnitOfWork
from src.core.security.dto import CurrentUser

log = logging.getLogger(__name__)


class MemberService:
    """Участники проекта и их роли.

    Тронуть участника и назначить роль можно, только если права его роли и новой
    роли есть у тебя: так admin не трогает owner'а без особых случаев в коде.
    Свою роль не меняют; выйти из проекта может любой участник. Последний
    владелец (право `ownership.manage`) не уходит и не теряет роль.
    """

    def __init__(self, uow: UnitOfWork, access: ProjectAccess) -> None:
        self._uow = uow
        self._access = access

    async def list_members(
        self, current_user: CurrentUser, project_id: UUID
    ) -> tuple[MemberDTO, ...]:
        await self._access.require(project_id, current_user, Permission.PROJECT_READ)
        members = await self._uow.memberships.list_for_project(project_id)
        return tuple(MemberDTO.from_orm(member) for member in members)

    async def list_roles(self, current_user: CurrentUser, project_id: UUID) -> tuple[RoleDTO, ...]:
        await self._access.require(project_id, current_user, Permission.PROJECT_READ)
        return tuple(RoleDTO.from_orm(role) for role in await self._uow.roles.list_all())

    async def change_role(
        self, current_user: CurrentUser, project_id: UUID, user_id: UUID, role_key: str
    ) -> MemberDTO:
        granter = await self._access.require(project_id, current_user, Permission.MEMBER_MANAGE)
        if user_id == current_user.user_id:
            raise OwnRoleChangeError({"project_id": str(project_id)})
        member = await self._get_member(project_id, user_id)
        self._access.require_grantable(granter, member.role.permissions, member.role.key)
        role = await self._uow.roles.get_by_key(role_key)
        if role is None:
            raise RoleInvalidError({"role": role_key}, {"role": role_key})
        self._access.require_grantable(granter, role.permissions, role.key)
        if Permission.OWNERSHIP_MANAGE not in role.permissions:
            await self._keep_an_owner(member)
        member.role_id = role.id
        member.role = role
        await self._access.record_change(project_id)
        await self._uow.commit()
        await self._access.publish(project_id, user_id)
        log.info(
            "Роль участника изменена",
            extra={
                "event": "member.role_changed",
                "project_id": str(project_id),
                "member_id": str(user_id),
                "role": role.key,
            },
        )
        return MemberDTO.from_orm(member)

    async def remove(self, current_user: CurrentUser, project_id: UUID, user_id: UUID) -> None:
        """Исключает участника; свой id — выход из проекта, для него права не нужны."""
        leaving = user_id == current_user.user_id
        if leaving:
            granter = await self._access.member_permissions(project_id, current_user)
        else:
            granter = await self._access.require(project_id, current_user, Permission.MEMBER_MANAGE)
        member = await self._get_member(project_id, user_id)
        if not leaving:
            self._access.require_grantable(granter, member.role.permissions, member.role.key)
        await self._keep_an_owner(member)
        await self._uow.memberships.delete(member)
        await self._access.record_change(project_id)
        await self._uow.commit()
        await self._access.publish(project_id, user_id)
        log.info(
            "Участник вышел из проекта" if leaving else "Участник исключён из проекта",
            extra={
                "event": "member.left" if leaving else "member.removed",
                "project_id": str(project_id),
                "member_id": str(user_id),
            },
        )

    async def _get_member(self, project_id: UUID, user_id: UUID) -> Membership:
        member = await self._uow.memberships.get_for_update(project_id, user_id)
        if member is None:
            raise MemberNotFoundError({"project_id": str(project_id), "member_id": str(user_id)})
        return member

    async def _keep_an_owner(self, member: Membership) -> None:
        if Permission.OWNERSHIP_MANAGE not in member.role.permissions:
            return
        owners = await self._uow.memberships.lock_holders(
            member.project_id, Permission.OWNERSHIP_MANAGE
        )
        if set(owners) <= {member.user_id}:
            raise LastOwnerError({"project_id": str(member.project_id)})
