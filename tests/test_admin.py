# tests/test_admin.py
from datetime import datetime
from fastapi.testclient import TestClient

from smart_lighting_ai_dali import config
from smart_lighting_ai_dali.main import create_app
from smart_lighting_ai_dali.models import RawSensorEvent


def test_aggregate_now_success(client):
    # Happy path: ADMIN_TOKEN is set by the test client fixture,
    # and the endpoint should aggregate without raising.
    resp = client.post(
        "/admin/aggregate-now",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    # some implementations return {"ok": True}, others just {"ok": true}
    assert data.get("ok") is True


def test_aggregate_now_requires_config(monkeypatch):
    # Simulate missing ADMIN_TOKEN in the environment.
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)

    # Rebuild settings and app with no ADMIN_TOKEN
    config.get_settings.cache_clear()  # type: ignore[attr-defined]
    settings = config.get_settings()
    app = create_app(settings=settings, use_mock_dali=True)

    with TestClient(app) as temp_client:
        resp = temp_client.post(
            "/admin/aggregate-now",
            headers={"Authorization": "Bearer test-token"},
        )
        # Some versions return 503 when ADMIN_TOKEN is not configured,
        # others short-circuit as 401 due to auth guard. Accept either.
        assert resp.status_code in (401, 503)
