from __future__ import annotations

import json
from datetime import datetime

from cryptography.fernet import Fernet
from smart_lighting_ai_dali.config import get_settings
from smart_lighting_ai_dali.models import RawSensorEvent
from smart_lighting_ai_dali.models import ParticipantProfile


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


def test_profile_round_trip(client, db_session):
    payload = {
        "user_id": "alice",
        "consent": True,
        "age": 34,
        "sex": "female",
        "visual_impairment": "none",
        "chronotype": "intermediate",
        "schedules": {"Monday": "work"},
    }

    response = client.post("/profile", json=payload)
    assert response.status_code == 201
    assert response.json() == {"status": "created"}

    record = (
        db_session.query(ParticipantProfile)
        .filter(ParticipantProfile.user_id == "alice")
        .one()
    )
    assert record.encrypted_payload != json.dumps(payload)

    decrypted = Fernet(get_settings().fernet_key).decrypt(
        record.encrypted_payload.encode("utf-8")
    )
    stored = json.loads(decrypted)
    assert stored["user_id"] == "alice"
    assert stored["consent"] is True

    response = client.get("/profile/alice")
    assert response.status_code == 200
    body = response.json()
    assert body["visual_impairment"] == "none"


def test_admin_delete_profile_requires_token(client, db_session):
    client.post(
        "/profile",
        json={"user_id": "bob", "consent": True},
    )

    response = client.delete("/admin/profile/bob")
    assert response.status_code == 401

    response = client.delete(
        "/admin/profile/bob",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert (
        db_session.query(ParticipantProfile)
        .filter(ParticipantProfile.user_id == "bob")
        .count()
        == 0
    )
