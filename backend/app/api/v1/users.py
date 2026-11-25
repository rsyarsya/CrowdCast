from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import AdminUser, DbSession, require_admin
from app.models import User
from app.schemas.auth import UserCreate, UserOut, UserUpdate
from app.services import users
from app.services.users import UserError

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])

ERROR_STATUS = {
    "email_already_exists": status.HTTP_409_CONFLICT,
    "cannot_modify_self": status.HTTP_422_UNPROCESSABLE_CONTENT,
}


def to_http(error: UserError) -> HTTPException:
    return HTTPException(ERROR_STATUS[error.code], detail=error.code)


async def get_user_or_404(db: DbSession, user_id: Annotated[int, Path()]) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="user_not_found")
    return user


@router.get("", response_model=list[UserOut])
async def list_users(db: DbSession) -> list[UserOut]:
    return [UserOut.from_model(user) for user in await users.list_users(db)]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(db: DbSession, body: UserCreate) -> UserOut:
    try:
        return UserOut.from_model(await users.create_user(db, body))
    except UserError as error:
        raise to_http(error) from error


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    db: DbSession,
    admin: AdminUser,
    body: UserUpdate,
    user: Annotated[User, Depends(get_user_or_404)],
) -> UserOut:
    """Change name, role, password, or `is_active`. Deactivating replaces deletion."""
    try:
        return UserOut.from_model(await users.update_user(db, user, body, admin))
    except UserError as error:
        raise to_http(error) from error
