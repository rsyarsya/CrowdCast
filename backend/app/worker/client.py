"""HTTP client for the API ingest endpoints (/api/v1/ingest/cameras/{camera_id})."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.services.vision.types import CrowdStatus, IntervalRecord, LiveState
from app.worker.forecasting import ForecastPoint


class IngestClient:
    def __init__(self, api_url: str, camera_id: str, worker_key: str, timeout: float = 5.0) -> None:
        base = f"{api_url.rstrip('/')}/api/v1/ingest/cameras/{quote(camera_id, safe='')}"
        self._http = httpx.Client(base_url=base, headers={"X-Worker-Key": worker_key}, timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def get_config(self) -> dict[str, Any]:
        response = self._http.get("/config")
        response.raise_for_status()
        return response.json()

    def post_records(self, records: list[tuple[IntervalRecord, CrowdStatus]]) -> None:
        body = {
            "records": [
                {"timestamp": r.start.isoformat(), "people_count": r.people_count, "crowd_status": status}
                for r, status in records
            ]
        }
        self._http.post("/records", json=body).raise_for_status()

    def get_recent_records(self, limit: int = 180) -> list[tuple[datetime, int]]:
        response = self._http.get("/records/recent", params={"limit": limit})
        response.raise_for_status()
        return [(datetime.fromisoformat(r["timestamp"]), r["people_count"]) for r in response.json()]

    def post_predictions(self, predictions: list[ForecastPoint]) -> None:
        body = {
            "predictions": [
                {
                    "timestamp": p.timestamp.isoformat(),
                    "horizon_minutes": p.horizon_minutes,
                    "predicted_count": p.predicted_count,
                    "predicted_status": p.predicted_status,
                    "model_name": p.model_name,
                }
                for p in predictions
            ]
        }
        self._http.post("/predictions", json=body).raise_for_status()

    def put_live(self, live: LiveState) -> None:
        body = {
            "timestamp": live.timestamp.isoformat(),
            "raw_count": live.raw_count,
            "smoothed_count": live.smoothed_count,
            "crowd_status": live.crowd_status,
        }
        self._http.put("/live", json=body).raise_for_status()

    def put_frame(self, jpeg: bytes) -> None:
        self._http.put("/frame", content=jpeg, headers={"Content-Type": "image/jpeg"}).raise_for_status()
