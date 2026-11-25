from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.security import create_access_token
from app.schemas.auth import Token, UserOut
from app.services import users

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=Token,
    responses={401: {"description": "invalid_credentials"}},
)
async def login(
    db: DbSession, form: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """OAuth2 password login. `username` is the user's email address.

    The same error is returned for an unknown email, a wrong password, and an
    inactive account, so the response does not reveal which emails exist.
    """
    user = await users.authenticate(db, form.username, form.password)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    expires_in = get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60
    return Token(
        access_token=create_access_token(subject=user.id, role=user.role.value),
        expires_in=expires_in,
    )


@router.get("/me", response_model=UserOut)
async def read_me(user: CurrentUser) -> UserOut:
    return UserOut.from_model(user)
