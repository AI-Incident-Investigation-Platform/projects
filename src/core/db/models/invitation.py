from datetime import datetime
from uuid import UUID, uuid7

from sqlalchemy import ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.enums import InvitationStatus
from src.core.db.models.base import Base
from src.core.db.models.project import Project
from src.core.db.models.role import Role


class Invitation(Base):
    """Приглашение зарегистрированного пользователя в проект с ролью.

    Ответ на приглашение не удаляет строку: видно, кто кого звал и чем кончилось.
    Ждущее приглашение с прошедшим `expires_at` недействительно сразу, а статус
    `expired` получает, когда его коснётся следующий запрос.
    """

    __table_args__ = (
        # одно ждущее приглашение на человека в проекте: повторное — конфликт, а не дубль письма
        Index(
            "uq_invitations_project_id_user_id_pending",
            "project_id",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    # пользователь живёт в БД auth и users, поэтому без внешнего ключа
    user_id: Mapped[UUID] = mapped_column(index=True)
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id"))
    invited_by: Mapped[UUID]
    status: Mapped[InvitationStatus] = mapped_column(server_default=InvitationStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    responded_at: Mapped[datetime | None]

    project: Mapped[Project] = relationship(lazy="raise")
    role: Mapped[Role] = relationship(lazy="raise")
