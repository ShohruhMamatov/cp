from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user import User


class Role(str, enum.Enum):
    OWNER = "owner"
    PARTICIPANT = "participant"


class Membership(Base):
    """Access is a many-to-many relation that carries an attribute (the role),
    so it needs its own table rather than a plain association table."""

    __tablename__ = "memberships"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[Role] = mapped_column(
        # values_callable stores 'owner' / 'participant' rather than the
        # enum *names* ('OWNER' / 'PARTICIPANT') in Postgres.
        Enum(Role, name="role_enum", values_callable=lambda e: [m.value for m in e]),
        default=Role.PARTICIPANT,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="memberships")
    project: Mapped[Project] = relationship(back_populates="memberships")
