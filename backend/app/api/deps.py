from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

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
