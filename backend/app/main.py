from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.api.v1 import api_router
from app.core.config import get_settings
from app.db.session import create_engine, create_sessionmaker
from app.services.live import LiveHub
from app.services.login_limiter import LoginLimiter


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Create the engine inside the running event loop and dispose it on shutdown.
    engine = create_engine(get_settings())
    app.state.engine = engine
    app.state.sessionmaker = create_sessionmaker(engine)
    app.state.live_hub = LiveHub()
    settings = get_settings()
    app.state.login_limiter = LoginLimiter(settings.LOGIN_MAX_FAILURES, settings.LOGIN_WINDOW_SECONDS)
    try:
        yield
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(api_router, prefix=settings.API_V1_STR)
    return app


app = create_app()
