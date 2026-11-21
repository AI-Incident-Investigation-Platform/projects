from uuid import UUID, uuid7

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db.models.base import Base


class Role(Base):
    """Набор прав внутри проекта. Встроенные роли заводит миграция."""

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    key: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    permissions: Mapped[list[str]] = mapped_column(ARRAY(String(64)))
    # растёт с каждой миграцией, меняющей права роли: по ней Dragonfly отбрасывает старую запись
    version: Mapped[int] = mapped_column(server_default="1")
