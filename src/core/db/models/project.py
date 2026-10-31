from datetime import datetime
from uuid import UUID, uuid7

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db.models.base import Base


class Project(Base):
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(server_default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    archived_at: Mapped[datetime | None]
