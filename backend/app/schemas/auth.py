from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.models import User, UserRole

PASSWORD_MIN_LENGTH = 8
# bcrypt only uses the first 72 bytes of a password.
PASSWORD_MAX_LENGTH = 72

# A light format check: local addresses such as admin@crowdcast.local are valid
# accounts here, so strict deliverability rules do not apply.
Email = Annotated[
    str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=120)
]


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    # Seconds until the token expires; the frontend uses it as the cookie max age.
    expires_in: int


class UserOut(BaseModel):
    """A user as returned by the API. The password hash is never included."""

    id: int
    email: str
    name: str
    role: UserRole
    is_active: bool

    @classmethod
    def from_model(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
        )


class UserCreate(BaseModel):
    email: Email
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    role: UserRole = UserRole.OPERATOR


class UserUpdate(BaseModel):
    """Partial update: only the fields that are sent are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    password: str | None = Field(
        default=None, min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )
    role: UserRole | None = None
    is_active: bool | None = None
