from fastapi import APIRouter

from app.api.v1 import alerts, auth, camera_admin, cameras, ingest, prediction_accuracy, realtime, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(cameras.router)
api_router.include_router(prediction_accuracy.router)
api_router.include_router(camera_admin.router)
api_router.include_router(users.router)
api_router.include_router(alerts.router)
api_router.include_router(realtime.router)
# Worker routes use the X-Worker-Key header, not user login.
api_router.include_router(ingest.router)
