from typing import TYPE_CHECKING

from sqlalchemy import JSON, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.crowd_record import CrowdRecord
    from app.models.prediction import Prediction


class Camera(TimestampMixin, Base):
    """A camera or recorded-video source and its counting configuration."""

    __tablename__ = "cameras"
    __table_args__ = (
        CheckConstraint("threshold_normal >= 0", name="threshold_normal_nonnegative"),
        CheckConstraint(
            "threshold_ramai > threshold_normal", name="threshold_order"
        ),
    )

    # Internal key used by foreign keys; never shown to the frontend.
    id: Mapped[int] = mapped_column(primary_key=True)
    # Public identifier, exposed by the API as camera_id (for example "CAM-01").
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    location: Mapped[str] = mapped_column(String(150))
    # File path of a recorded video or an RTSP URL. May contain credentials,
    # so API responses must not return it to non-admin users.
    source: Mapped[str] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(default=True)

    # people_count >= threshold_normal -> Normal; >= threshold_ramai -> Ramai.
    threshold_normal: Mapped[int]
    threshold_ramai: Mapped[int]
    # Region of interest polygon as [[x, y], ...] normalized to 0..1;
    # None means the whole frame is counted.
    roi: Mapped[list[list[float]] | None] = mapped_column(JSON)

    records: Mapped[list["CrowdRecord"]] = relationship(
        back_populates="camera", passive_deletes=True
    )
    predictions: Mapped[list["Prediction"]] = relationship(
        back_populates="camera", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"Camera(code={self.code!r}, location={self.location!r})"
