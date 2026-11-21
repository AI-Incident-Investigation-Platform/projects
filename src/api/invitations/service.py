import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from src.api.exc.invitations import (
    AlreadyMemberError,
    InvitationGoneError,
    InvitationNotFoundError,
    InvitationPendingError,
    InvitationRoleInvalidError,
    InviteeInvalidError,
)
from src.config import cfg
from src.core.access.service import ProjectAccess
from src.core.db.dto.invitation import InvitationDTO
from src.core.db.dto.project import ProjectDTO
from src.core.db.dto.role import RoleDTO
from src.core.db.enums import InvitationStatus, Permission
from src.core.db.exc import IntegrityViolationError
from src.core.db.models.invitation import Invitation
from src.core.db.models.membership import Membership
from src.core.db.uow import UnitOfWork
from src.core.email.dto import EmailLetter
from src.core.email.enums import EmailTemplate
from src.core.email.service import EmailService
from src.core.errors import ErrorReport, IntegrationError, InternalError
from src.core.security.dto import CurrentUser
from src.core.users.dto import UserProfile
from src.core.users.service import UsersService

log = logging.getLogger(__name__)


class InvitationService:
    """Приглашения в проект: зовут зарегистрированного пользователя по id, он принимает сам.

    Приглашение — запись в БД, письмо — только уведомление: оно ставится после
    commit, и его сбой приглашение не отменяет, оно видно во входящих в интерфейсе.
    Ответ на приглашение идемпотентен: повторное «принять» или «отклонить» не
    меняет исход.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        access: ProjectAccess,
        users: UsersService,
        email: EmailService,
    ) -> None:
        self._uow = uow
        self._access = access
        self._users = users
        self._email = email

    async def invite(
        self, current_user: CurrentUser, project_id: UUID, user_id: UUID, role_key: str
    ) -> InvitationDTO:
        granter = await self._access.require(project_id, current_user, Permission.MEMBER_MANAGE)
        role = await self._uow.roles.get_by_key(role_key)
        if role is None:
            raise InvitationRoleInvalidError({"role": role_key}, {"role": role_key})
        self._access.require_grantable(granter, role.permissions, role.key)
        if await self._uow.memberships.get_permissions(project_id, user_id) is not None:
            raise AlreadyMemberError({"project_id": str(project_id), "user_id": str(user_id)})
        project = await self._uow.projects.get_by_id(project_id)
        if project is None:
            raise InternalError({"project_id": str(project_id)})
        # откат закрывает чтение до похода в users и делает ORM-объекты недоступными
        project_dto, role_dto = ProjectDTO.from_orm(project), RoleDTO.from_orm(role)
        await self._uow.rollback()

        profiles = await self._users.get_profiles(
            current_user.access_token, {user_id, current_user.user_id}
        )
        if (invitee := profiles.get(user_id)) is None:
            raise InviteeInvalidError({"user_id": str(user_id)}, {"user_id": str(user_id)})

        now = datetime.now(UTC)
        await self._expire_stale(project_id, user_id, now)
        invitation = Invitation(
            project_id=project_id,
            user_id=user_id,
            role_id=role_dto.id,
            invited_by=current_user.user_id,
            status=InvitationStatus.PENDING,
            expires_at=now + timedelta(days=cfg.invitations.ttl_days),
        )
        self._uow.invitations.add(invitation)
        try:
            await self._uow.flush()
        except IntegrityViolationError as exc:
            if exc.constraint != "uq_invitations_project_id_user_id_pending":
                raise
            raise InvitationPendingError(
                {"project_id": str(project_id), "user_id": str(user_id)}
            ) from exc
        await self._uow.commit()
        result = InvitationDTO(
            id=invitation.id,
            project=project_dto,
            user_id=user_id,
            role=role_dto,
            invited_by=invitation.invited_by,
            status=invitation.status,
            created_at=invitation.created_at,
            expires_at=invitation.expires_at,
            responded_at=None,
        )
        log.info(
            "Пользователь приглашён в проект",
            extra={
                "event": "invitation.created",
                "project_id": str(project_id),
                "invitation_id": str(invitation.id),
                "invitee_id": str(user_id),
                "role": role_dto.key,
            },
        )
        await self._notify(result, invitee, profiles.get(current_user.user_id))
        return result

    async def list_for_project(
        self, current_user: CurrentUser, project_id: UUID
    ) -> tuple[InvitationDTO, ...]:
        await self._access.require(project_id, current_user, Permission.MEMBER_MANAGE)
        rows = await self._uow.invitations.list_pending_for_project(project_id, datetime.now(UTC))
        return tuple(InvitationDTO.from_orm(row) for row in rows)

    async def revoke(
        self, current_user: CurrentUser, project_id: UUID, invitation_id: UUID
    ) -> None:
        """Отзывает ждущее приглашение; приглашение с ответом не меняется."""
        await self._access.require(project_id, current_user, Permission.MEMBER_MANAGE)
        invitation = await self._uow.invitations.get_in_project_for_update(
            project_id, invitation_id
        )
        if invitation is None:
            raise InvitationNotFoundError({"invitation_id": str(invitation_id)})
        if invitation.status != InvitationStatus.PENDING:
            return
        invitation.status = InvitationStatus.REVOKED
        invitation.responded_at = datetime.now(UTC)
        await self._uow.commit()
        log.info(
            "Приглашение отозвано",
            extra={
                "event": "invitation.revoked",
                "project_id": str(project_id),
                "invitation_id": str(invitation_id),
            },
        )

    async def list_mine(self, current_user: CurrentUser) -> tuple[InvitationDTO, ...]:
        rows = await self._uow.invitations.list_pending_for_user(
            current_user.user_id, datetime.now(UTC)
        )
        return tuple(InvitationDTO.from_orm(row) for row in rows)

    async def accept(self, current_user: CurrentUser, invitation_id: UUID) -> InvitationDTO:
        """Делает пользователя участником с ролью приглашения.

        Уже участник остаётся со своей ролью: приглашение не повышает и не понижает.
        """
        invitation = await self._answerable(current_user, invitation_id, InvitationStatus.ACCEPTED)
        if invitation.status == InvitationStatus.PENDING:
            existing = await self._uow.memberships.get_permissions(
                invitation.project_id, invitation.user_id
            )
            if existing is None:
                self._uow.memberships.add(
                    Membership(
                        project_id=invitation.project_id,
                        user_id=invitation.user_id,
                        role_id=invitation.role_id,
                    )
                )
                await self._access.record_change(invitation.project_id)
            invitation.status = InvitationStatus.ACCEPTED
            invitation.responded_at = datetime.now(UTC)
            await self._uow.commit()
            if existing is None:
                await self._access.publish(invitation.project_id, invitation.user_id)
            log.info(
                "Приглашение принято",
                extra={
                    "event": "invitation.accepted",
                    "project_id": str(invitation.project_id),
                    "invitation_id": str(invitation.id),
                },
            )
        return InvitationDTO.from_orm(invitation)

    async def decline(self, current_user: CurrentUser, invitation_id: UUID) -> None:
        invitation = await self._answerable(current_user, invitation_id, InvitationStatus.DECLINED)
        if invitation.status == InvitationStatus.PENDING:
            invitation.status = InvitationStatus.DECLINED
            invitation.responded_at = datetime.now(UTC)
            await self._uow.commit()
            log.info(
                "Приглашение отклонено",
                extra={
                    "event": "invitation.declined",
                    "project_id": str(invitation.project_id),
                    "invitation_id": str(invitation.id),
                },
            )

    async def _answerable(
        self, current_user: CurrentUser, invitation_id: UUID, answer: InvitationStatus
    ) -> Invitation:
        """Приглашение текущему пользователю, на которое можно дать `answer`.

        Ждущее или уже с этим же ответом — повтор безопасен; иначе 410.
        """
        invitation = await self._uow.invitations.get_for_update(invitation_id)
        if invitation is None or invitation.user_id != current_user.user_id:
            raise InvitationNotFoundError({"invitation_id": str(invitation_id)})
        if invitation.status == answer:
            return invitation
        if invitation.status == InvitationStatus.PENDING and invitation.expires_at <= datetime.now(
            UTC
        ):
            invitation.status = InvitationStatus.EXPIRED
            await self._uow.commit()
        if invitation.status != InvitationStatus.PENDING:
            raise InvitationGoneError(
                {"invitation_id": str(invitation_id), "status": invitation.status.value}
            )
        return invitation

    async def _expire_stale(self, project_id: UUID, user_id: UUID, now: datetime) -> None:
        """Истёкшее ждущее приглашение помечается: иначе оно занимает место нового."""
        pending = await self._uow.invitations.get_pending_for_update(project_id, user_id)
        if pending is not None and pending.expires_at <= now:
            pending.status = InvitationStatus.EXPIRED

    async def _notify(
        self, invitation: InvitationDTO, invitee: UserProfile, inviter: UserProfile | None
    ) -> None:
        inviter_name = (inviter.display_name or inviter.username) if inviter else "Участник AIIP"
        try:
            await self._email.send(
                EmailLetter(
                    template=EmailTemplate.INVITATION,
                    to=invitee.email,
                    params={
                        "inviter_name": inviter_name,
                        "project_name": invitation.project.name,
                        "role_name": invitation.role.name,
                        "accept_url": cfg.invitations.accept_url,
                        "expires_in_days": cfg.invitations.ttl_days,
                    },
                    ttl_seconds=cfg.invitations.letter_ttl_seconds,
                )
            )
        except IntegrationError as exc:
            log.warning(
                "Письмо с приглашением не поставлено, приглашение видно в интерфейсе",
                extra={
                    "event": "invitation.letter_failed",
                    "invitation_id": str(invitation.id),
                    "error": ErrorReport.from_exception(exc).to_log(),
                },
            )
