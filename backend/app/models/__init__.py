"""Import every model here so Base.metadata knows all tables (used by Alembic)."""

from app.models.alert import Alert
from app.models.camera import Camera
from app.models.crowd_record import CrowdRecord
from app.models.enums import AlertKind, CrowdStatus, UserRole
from app.models.prediction import Prediction
from app.models.user import User

__all__ = ["Alert", "AlertKind", "Camera", "CrowdRecord", "CrowdStatus", "Prediction", "User", "UserRole"]
