from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CrowdStatus, string_enum

if TYPE_CHECKING:
    from app.models.camera import Camera


class CrowdRecord(Base):
    """One aggregated observation of a camera (one row per interval)."""

    __tablename__ = "crowd_records"
    __table_args__ = (
        # Also serves as the (camera_id, timestamp) index for history queries.
        UniqueConstraint("camera_id", "timestamp"),
        CheckConstraint("people_count >= 0", name="people_count_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE")
    )
    # Observation time (not insert time), stored as UTC timestamptz.
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    people_count: Mapped[int]
    crowd_status: Mapped[CrowdStatus] = mapped_column(
        string_enum(CrowdStatus, "crowd_status")
    )

    camera: Mapped["Camera"] = relationship(back_populates="records")
