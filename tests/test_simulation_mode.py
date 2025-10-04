from __future__ import annotations

import logging
from datetime import datetime, timedelta

from smart_lighting_ai_dali.dali import MockDALIController
from smart_lighting_ai_dali.feature_engineering import aggregate_features
from smart_lighting_ai_dali.models import Decision, RawSensorEvent, WeatherEvent
from smart_lighting_ai_dali.retention import prune_old_data


def _seed_features(db_session) -> None:  # noqa: ANN001
    now = datetime.utcnow()
    db_session.add_all(
        [
            RawSensorEvent(ambient_lux=220, presence=True, timestamp=now - timedelta(minutes=3)),
            RawSensorEvent(ambient_lux=180, presence=True, timestamp=now - timedelta(minutes=2)),
            RawSensorEvent(ambient_lux=260, presence=False, timestamp=now - timedelta(minutes=1)),
        ]
    )
    db_session.add(
        WeatherEvent(weather_summary="Overcast", temperature_c=15.0, timestamp=now)
    )
    db_session.commit()
    aggregate_features(db_session, window_minutes=5)


def test_simulation_predict_control_flow(client, db_session, caplog):  # noqa: ANN001
    _seed_features(db_session)
    caplog.set_level(logging.INFO, logger="smart_lighting_ai_dali.dali.interface")

    predict_response = client.post("/predict", json={})
    assert predict_response.status_code == 200

    control_response = client.post(
        "/control",
        json={"intensity": 55, "cct": 4100, "reason": "sim", "source": "test"},
    )
    assert control_response.status_code == 200
    assert control_response.json()["applied"] is True

    controller = client.app.state.control_service.dali
    assert isinstance(controller, MockDALIController)
    assert any("Mock DALI applied setpoint" in record.getMessage() for record in caplog.records)


def test_simulation_telemetry_pagination(client, db_session):  # noqa: ANN001
    for idx in range(3):
        response = client.post(
            "/control",
            json={"intensity": 40 + idx * 5, "cct": 3900, "reason": "batch", "source": "test"},
        )
        assert response.status_code == 200

    first_page = client.get("/telemetry", params={"limit": 1, "offset": 0})
    assert first_page.status_code == 200
    payload = first_page.json()
    assert payload["next_offset"] == 1

    second_page = client.get("/telemetry", params={"limit": 1, "offset": payload["next_offset"]})
    assert second_page.status_code == 200
    assert len(second_page.json()["items"]) == 1

    total_decisions = db_session.query(Decision).count()
    assert total_decisions >= 3


def test_jobs_safe_on_empty_database(db_session):  # noqa: ANN001
    result = aggregate_features(db_session, window_minutes=5)
    assert result is None

    counts = prune_old_data(db_session)
    assert counts["raw"] == 0
    assert counts["features"] == 0
    assert counts["decisions"] == 0
