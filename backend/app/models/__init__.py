"""Import every model here so Base.metadata knows all tables (used by Alembic)."""

from app.models.camera import Camera
from app.models.crowd_record import CrowdRecord
from app.models.enums import CrowdStatus, UserRole
from app.models.prediction import Prediction
from app.models.user import User

__all__ = ["Camera", "CrowdRecord", "CrowdStatus", "Prediction", "User", "UserRole"]
