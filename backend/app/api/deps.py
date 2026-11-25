from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.models import User, UserRole
from app.services.live import LiveHub


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield one database session per request and always close it."""
    sessionmaker = request.app.state.sessionmaker
    async with sessionmaker() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_live_hub(request: Request) -> LiveHub:
    """The in-memory live state and frame hub created in the app lifespan."""
    return request.app.state.live_hub


LiveHubDep = Annotated[LiveHub, Depends(get_live_hub)]


# auto_error=False so a missing token returns our own error code.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def unauthorized(code: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail=code,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    db: DbSession, token: Annotated[str | None, Depends(oauth2_scheme)]
) -> User:
    """The user behind the Bearer token.

    The user is loaded from the database on every request, so a role change or
    deactivation takes effect immediately even while an old token is valid.
    """
    if token is None:
        raise unauthorized("not_authenticated")
    payload = decode_access_token(token)
    subject = payload.get("sub") if payload else None
    if subject is None or not str(subject).isdigit():
        raise unauthorized("invalid_token")
    user = await db.get(User, int(subject))
    if user is None or not user.is_active:
        raise unauthorized("invalid_token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role is not UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="forbidden")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
