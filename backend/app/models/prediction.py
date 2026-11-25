from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CrowdStatus, string_enum

if TYPE_CHECKING:
    from app.models.camera import Camera


class Prediction(Base):
    """Forecast of a camera's crowd `horizon_minutes` after `timestamp`."""

    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint("horizon_minutes > 0", name="horizon_positive"),
        CheckConstraint("predicted_count >= 0", name="predicted_count_nonnegative"),
        Index(
            "ix_predictions_camera_horizon_timestamp",
            "camera_id",
            "horizon_minutes",
            "timestamp",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE")
    )
    # When the prediction was made; the target time is timestamp + horizon.
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    horizon_minutes: Mapped[int]
    predicted_count: Mapped[int]
    predicted_status: Mapped[CrowdStatus] = mapped_column(
        string_enum(CrowdStatus, "predicted_status")
    )
    # Which forecaster produced it (for example "moving_average").
    model_name: Mapped[str] = mapped_column(String(50))
    # True for mock/simulated values so the UI can keep labeling them.
    is_simulation: Mapped[bool] = mapped_column(default=False)

    camera: Mapped["Camera"] = relationship(back_populates="predictions")
