from fastapi import APIRouter

from app.api.v1 import cameras, ingest

api_router = APIRouter()
api_router.include_router(cameras.router)
api_router.include_router(ingest.router)
