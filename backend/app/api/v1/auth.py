from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession, LoginLimiterDep
from app.core.config import get_settings
from app.core.security import create_access_token
from app.schemas.auth import Token, UserOut
from app.services import users

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=Token,
    responses={
        401: {"description": "invalid_credentials"},
        429: {"description": "too_many_attempts, see Retry-After"},
    },
)
async def login(
    request: Request,
    db: DbSession,
    limiter: LoginLimiterDep,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """OAuth2 password login. `username` is the user's email address.

    The same error is returned for an unknown email, a wrong password, and an
    inactive account, so the response does not reveal which emails exist.
    """
    client = request.client.host if request.client else "unknown"
    key = f"{client}|{form.username.strip().lower()}"
    retry_after = limiter.retry_after(key)
    if retry_after is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too_many_attempts",
            headers={"Retry-After": str(retry_after)},
        )
    user = await users.authenticate(db, form.username, form.password)
    if user is None:
        limiter.record_failure(key)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    limiter.reset(key)
    expires_in = get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60
    return Token(
        access_token=create_access_token(subject=user.id, role=user.role.value),
        expires_in=expires_in,
    )


@router.get("/me", response_model=UserOut)
async def read_me(user: CurrentUser) -> UserOut:
    return UserOut.from_model(user)
