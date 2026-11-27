from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AlertKind, string_enum

if TYPE_CHECKING:
    from app.models.camera import Camera
    from app.models.user import User


class Alert(Base):
    """A period during which a camera was, or was forecast to be, Ramai.

    An alert stays open (ended_at is null) until a later record or forecast
    for the same camera, kind, and horizon is no longer Ramai.
    """

    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("peak_count >= 0", name="peak_count_nonnegative"),
        CheckConstraint(
            "(kind = 'crowded') = (horizon_minutes IS NULL)", name="horizon_matches_kind"
        ),
        Index(
            "uq_alerts_open",
            "camera_id",
            "kind",
            "horizon_minutes",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_alerts_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"))
    kind: Mapped[AlertKind] = mapped_column(string_enum(AlertKind, "alert_kind"))
    horizon_minutes: Mapped[int | None]
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    peak_count: Mapped[int]
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    camera: Mapped["Camera"] = relationship()
    acknowledged_by: Mapped["User | None"] = relationship()
