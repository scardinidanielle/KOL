from __future__ import annotations

from datetime import datetime, timedelta

from smart_lighting_ai_dali.feature_engineering import aggregate_features, prepare_feature_windows
from smart_lighting_ai_dali.models import RawSensorEvent, WeatherEvent


def test_ingest_sensor_and_weather(client, db_session):
    response = client.post("/ingest/sensor", json={"ambient_lux": 200, "presence": True})
    assert response.status_code == 201
    response = client.post(
        "/ingest/weather",
        json={
            "weather_summary": "Overcast",
            "temperature_c": 10,
        },
    )
    assert response.status_code == 201

    events = db_session.query(RawSensorEvent).all()
    assert len(events) == 1
    weather = db_session.query(WeatherEvent).all()
    assert len(weather) == 1


def test_feature_aggregation_creates_row(db_session):
    now = datetime.utcnow()
    db_session.add_all(
        [
            RawSensorEvent(
                ambient_lux=100,
                presence=True,
                timestamp=now - timedelta(minutes=2),
            ),
            RawSensorEvent(
                ambient_lux=200,
                presence=False,
                timestamp=now - timedelta(minutes=1),
            ),
        ]
    )
    db_session.add(
        WeatherEvent(weather_summary="Cloudy", temperature_c=12, timestamp=now)
    )
    db_session.commit()

    feature = aggregate_features(db_session, window_minutes=5)
    assert feature is not None
    assert feature.ambient_lux_mean >= 100

    windows = prepare_feature_windows(db_session, rows=3)
    assert 1 <= len(windows) <= 3
    payload_size = len(str(windows[-1]).encode("utf-8"))
    assert payload_size < 1024
