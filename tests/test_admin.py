from __future__ import annotations

from fastapi.testclient import TestClient

from smart_lighting_ai_dali import config
from smart_lighting_ai_dali.main import create_app


def test_aggregate_now_success(client):
    response = client.post(
        "/admin/aggregate-now",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_aggregate_now_missing_token(client):
    response = client.post("/admin/aggregate-now")
    assert response.status_code == 401
    assert response.json() == {"detail": "Missing or invalid token"}


def test_aggregate_now_wrong_token(client):
    response = client.post(
        "/admin/aggregate-now",
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}


def test_aggregate_now_requires_config(monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    config.get_settings.cache_clear()  # type: ignore[attr-defined]
    settings = config.get_settings()
    app = create_app(settings=settings, use_mock_dali=True)
    with TestClient(app) as temp_client:
        response = temp_client.post(
            "/admin/aggregate-now",
            headers={"Authorization": "Bearer test-token"},
        )
    assert response.status_code == 503
    assert response.json() == {"detail": "Admin token not configured"}
    config.get_settings.cache_clear()  # type: ignore[attr-defined]
