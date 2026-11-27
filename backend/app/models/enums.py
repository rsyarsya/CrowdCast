import enum

from sqlalchemy import Enum


class CrowdStatus(str, enum.Enum):
    """Official crowd status terms, spelled exactly as the frontend expects."""

    SEPI = "Sepi"
    NORMAL = "Normal"
    RAMAI = "Ramai"


class AlertKind(str, enum.Enum):
    CROWDED = "crowded"
    FORECAST_CROWDED = "forecast_crowded"


class UserRole(str, enum.Enum):
    OPERATOR = "operator"
    ADMIN = "admin"


def string_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Store enum *values* as VARCHAR guarded by a CHECK constraint.

    native_enum=False avoids a PostgreSQL ENUM type, so adding a value later is
    a plain constraint change instead of ALTER TYPE.
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=20,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )
