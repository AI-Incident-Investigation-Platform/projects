from datetime import datetime
from uuid import UUID, uuid7

from sqlalchemy import ForeignKey, ForeignKeyConstraint, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db.models.base import Base


class MonitoredService(Base):
    """Сервис наблюдаемого приложения в среде проекта; в API — Service."""

    __table_args__ = (
        ForeignKeyConstraint(
            ["environment_id", "project_id"],
            ["environments.id", "environments.project_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("environment_id", "name"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    environment_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(String(160))
    external_names: Mapped[list[str]] = mapped_column(ARRAY(String(160)), server_default="{}")
    description: Mapped[str] = mapped_column(server_default="")
    repository_url: Mapped[str | None] = mapped_column(String(2048))
    health_url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
