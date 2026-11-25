"""User management rules. Raises `UserError` with a stable code on violations."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password_or_dummy
from app.models import User, UserRole
from app.schemas.auth import UserCreate, UserUpdate


class UserError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    """The active user with these credentials, or None for any failure."""
    user = await session.scalar(select(User).where(func.lower(User.email) == email.lower()))
    valid = verify_password_or_dummy(password, user.hashed_password if user else None)
    if user is None or not valid or not user.is_active:
        return None
    return user


async def list_users(session: AsyncSession) -> Sequence[User]:
    return (await session.scalars(select(User).order_by(User.id))).all()


async def create_user(session: AsyncSession, data: UserCreate) -> User:
    user = User(
        email=data.email.lower(),
        name=data.name,
        hashed_password=get_password_hash(data.password),
        role=data.role,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise UserError("email_already_exists") from exc
    return user


async def update_user(
    session: AsyncSession, user: User, data: UserUpdate, acting_admin: User
) -> User:
    changes = data.model_dump(exclude_unset=True)
    loses_admin = changes.get("is_active") is False or (
        changes.get("role") is not None and changes["role"] is not UserRole.ADMIN
    )
    # The acting admin is always an active admin, so forbidding self-demotion
    # and self-deactivation also guarantees that one active admin remains.
    if loses_admin and user.id == acting_admin.id:
        raise UserError("cannot_modify_self")

    if "name" in changes and changes["name"] is not None:
        user.name = changes["name"]
    if "role" in changes and changes["role"] is not None:
        user.role = changes["role"]
    if "is_active" in changes and changes["is_active"] is not None:
        user.is_active = changes["is_active"]
    if "password" in changes and changes["password"] is not None:
        user.hashed_password = get_password_hash(changes["password"])
    await session.commit()
    return user
