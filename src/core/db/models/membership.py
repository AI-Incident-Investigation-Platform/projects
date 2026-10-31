from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.models.base import Base
from src.core.db.models.role import Role


class Membership(Base):
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    # пользователь живёт в БД auth, поэтому без внешнего ключа
    user_id: Mapped[UUID] = mapped_column(primary_key=True, index=True)
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    role: Mapped[Role] = relationship(lazy="raise")
