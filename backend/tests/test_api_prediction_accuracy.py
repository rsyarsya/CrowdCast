from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Camera, CrowdRecord, CrowdStatus, Prediction
from app.scripts.evaluate_predictions import format_report
from app.services.prediction_accuracy import prediction_accuracy

pytestmark = pytest.mark.anyio

API = "/api/v1/cameras"
UTC = timezone.utc
T0 = datetime(2026, 9, 23, 3, 0, tzinfo=UTC)
END = (T0 + timedelta(minutes=30)).isoformat()


def status_of(count: int) -> CrowdStatus:
    return CrowdStatus.RAMAI if count >= 12 else CrowdStatus.NORMAL if count >= 4 else CrowdStatus.SEPI


async def seed(session: AsyncSession) -> Camera:
    """Counts 0..20 one per minute; 5-minute forecasts that are always 2 too high,
    plus a simulated one and one whose target time has no record yet."""
    camera = Camera(
        code="CAM-02",
        name="Kabukicho",
        location="Tokyo",
        source="video.mp4",
        threshold_normal=4,
        threshold_ramai=12,
    )
    session.add(camera)
    await session.flush()
    for minute in range(21):
        session.add(
            CrowdRecord(
                camera_id=camera.id,
                timestamp=T0 + timedelta(minutes=minute),
                people_count=minute,
                crowd_status=status_of(minute),
            )
        )
    for minute in range(17):
        predicted = minute + 5 + 2
        session.add(
            Prediction(
                camera_id=camera.id,
                timestamp=T0 + timedelta(minutes=minute),
                horizon_minutes=5,
                predicted_count=predicted,
                predicted_status=status_of(predicted),
                model_name="moving_average_5",
            )
        )
    session.add(
        Prediction(
            camera_id=camera.id,
            timestamp=T0,
            horizon_minutes=15,
            predicted_count=0,
            predicted_status=CrowdStatus.SEPI,
            model_name="mock",
            is_simulation=True,
        )
    )
    await session.commit()
    return camera


async def test_service_scores_only_matched_real_predictions(db_session: AsyncSession) -> None:
    camera = await seed(db_session)
    results = await prediction_accuracy(db_session, camera, T0, T0 + timedelta(minutes=30))
    assert [r.horizon_minutes for r in results] == [5]
    s = results[0].score
    assert s.samples == 16
    assert (s.mae, s.rmse, s.bias) == (2.0, 2.0, 2.0)
    assert s.status_accuracy == pytest.approx(14 / 16)
    assert results[0].model_names == ["moving_average_5"]

    with_mock = await prediction_accuracy(
        db_session, camera, T0, T0 + timedelta(minutes=30), include_simulation=True
    )
    assert [r.horizon_minutes for r in with_mock] == [5, 15]
    assert "moving_average_5" in format_report(results)


async def test_window_limits_target_times(db_session: AsyncSession) -> None:
    camera = await seed(db_session)
    results = await prediction_accuracy(
        db_session, camera, T0 + timedelta(minutes=18), T0 + timedelta(minutes=20)
    )
    assert results[0].score.samples == 3


async def test_accuracy_endpoint(
    client: TestClient, db_session: AsyncSession, operator_headers: dict[str, str]
) -> None:
    await seed(db_session)
    response = client.get(
        f"{API}/CAM-02/predictions/accuracy",
        params={"hours": 1, "end": END},
        headers=operator_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["camera_id"] == "CAM-02"
    assert body["end"] == "2026-09-23T10:30:00+07:00"
    assert body["horizons"] == [
        {
            "horizon_minutes": 5,
            "samples": 16,
            "mae": 2.0,
            "rmse": 2.0,
            "bias": 2.0,
            "status_accuracy": 0.875,
            "model_names": ["moving_average_5"],
        }
    ]


async def test_accuracy_endpoint_empty_and_errors(
    client: TestClient, db_session: AsyncSession, operator_headers: dict[str, str]
) -> None:
    await seed(db_session)
    url = f"{API}/CAM-02/predictions/accuracy"
    empty = client.get(url, params={"end": "2026-01-01T00:00:00+07:00"}, headers=operator_headers)
    assert empty.status_code == 200
    assert empty.json()["horizons"] == []
    assert client.get(url, params={"end": "2026-01-01T00:00:00"}, headers=operator_headers).status_code == 422
    assert client.get(url, params={"hours": 0}, headers=operator_headers).status_code == 422
    assert client.get(f"{API}/CAM-99/predictions/accuracy", headers=operator_headers).status_code == 404
    assert client.get(url).status_code == 401
