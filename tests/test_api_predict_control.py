from __future__ import annotations

from datetime import datetime, timedelta

from smart_lighting_ai_dali.feature_engineering import aggregate_features
from smart_lighting_ai_dali.models import RawSensorEvent, WeatherEvent


def seed_features(db_session):
    now = datetime.utcnow()
    db_session.query(RawSensorEvent).delete()
    db_session.query(WeatherEvent).delete()
    db_session.add_all(
        [
            RawSensorEvent(
                ambient_lux=200,
                presence=True,
                timestamp=now - timedelta(minutes=3),
            ),
            RawSensorEvent(
                ambient_lux=150,
                presence=True,
                timestamp=now - timedelta(minutes=2),
            ),
            RawSensorEvent(
                ambient_lux=300,
                presence=False,
                timestamp=now - timedelta(minutes=1),
            ),
        ]
    )
    db_session.add(
        WeatherEvent(weather_summary="Overcast", temperature_c=15, timestamp=now)
    )
    db_session.commit()
    aggregate_features(db_session, window_minutes=5)


def test_predict_returns_setpoint(client, db_session):
    seed_features(db_session)
    response = client.post("/predict", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["setpoint"]["intensity_0_100"] >= 0
    assert data["features_used"] <= 3
    assert data["payload_bytes"] <= 2048


def test_control_endpoint_and_pagination(client, db_session):
    seed_features(db_session)
    client.post("/predict", json={})
    response = client.post(
        "/control",
        json={
            "intensity": 50,
            "cct": 4000,
            "reason": "test",
            "source": "ai",
        },
    )
    assert response.status_code == 200
    control_data = response.json()
    assert control_data["applied"] is True

    telemetry = client.get("/telemetry", params={"limit": 1, "offset": 0})
    assert telemetry.status_code == 200
    telemetry_data = telemetry.json()
    assert len(telemetry_data["items"]) == 1
    assert telemetry_data["next_offset"] is None or telemetry_data["next_offset"] >= 1
