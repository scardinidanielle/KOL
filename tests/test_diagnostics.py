from __future__ import annotations


def test_dali_diagnostics_reports_mode_and_status(client):
    response = client.get("/diagnostics/dali")
    assert response.status_code == 200
    data = response.json()

    assert data["mode"] == "mock"
    assert "status" in data["diagnostics"]
    assert data["supports_sensor_probe"] is True
    assert data["sensor_event_count"] == 0
    assert data["latest_sensor_event"] is None


def test_dali_diagnostics_reflects_latest_sensor_event(client):
    ingest_payload = {"ambient_lux": 420.5, "presence": True}
    ingest_response = client.post("/ingest/sensor", json=ingest_payload)
    assert ingest_response.status_code == 201

    response = client.get("/diagnostics/dali")
    assert response.status_code == 200
    data = response.json()

    assert data["sensor_event_count"] == 1
    latest = data["latest_sensor_event"]
    assert latest["presence"] is True
    assert latest["ambient_lux"] == ingest_payload["ambient_lux"]
