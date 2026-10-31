from datetime import datetime
from uuid import UUID, uuid7

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db.models.base import Base


class Environment(Base):
    __table_args__ = (
        UniqueConstraint("project_id", "slug"),
        # цель составного внешнего ключа сервиса: среда сервиса из того же проекта
        UniqueConstraint("id", "project_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    is_production: Mapped[bool] = mapped_column(server_default="false")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
