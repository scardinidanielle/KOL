from __future__ import annotations

from datetime import datetime

from smart_lighting_ai_dali.models import RawSensorEvent


def test_admin_aggregate_now_requires_auth(client):
    response = client.post("/admin/aggregate-now")
    assert response.status_code == 401


def test_admin_aggregate_now_creates_features(client, db_session):
    event = RawSensorEvent(
        ambient_lux=250,
        presence=True,
        timestamp=datetime.utcnow(),
    )
    db_session.add(event)
    db_session.commit()

    response = client.post(
        "/admin/aggregate-now",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"ok": True}
