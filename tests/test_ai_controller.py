from __future__ import annotations

import json

import pytest

from smart_lighting_ai_dali.openai_client import AIController, FeatureWindow


class FakeResponses:
    def __init__(self, payload):
        self.payload = payload

    def create(self, **kwargs):  # noqa: ANN001, ANN003
        class _Response:
            def __init__(self, payload):
                self.output = [[{"content": [{"text": json.dumps(payload)}]}]]

        return _Response(self.payload)


def test_payload_cap_enforced(monkeypatch):
    controller = AIController()
    big_payload = [
        FeatureWindow(payload={"ambient_lux": i, "occupancy": 1.0}, timestamp="0")
        for i in range(1000)
    ]
    with pytest.raises(ValueError):
        controller._build_payload(big_payload)  # type: ignore[arg-type]


def test_fallback_is_used_when_no_client():
    controller = AIController(settings=None, client=None)
    features = [
        FeatureWindow(payload={"ambient_lux": 100, "occupancy": 0.5}, timestamp="0")
    ]
    result, size = controller.compute_setpoint(features)
    assert result["intensity_0_100"] >= 0
    assert size <= controller.settings.payload_cap_bytes


def test_openai_response_is_clamped(monkeypatch):
    controller = AIController(client=None)
    controller.client = type(
        "Client",
        (),
        {
            "responses": FakeResponses(
                {"intensity_0_100": 150, "cct_1800_6500": 9000, "reason": "test"}
            )
        },
    )()
    features = [
        FeatureWindow(payload={"ambient_lux": 100, "occupancy": 1}, timestamp="0")
    ]
    result, _ = controller.compute_setpoint(features)
    assert result["intensity_0_100"] <= 100
    assert result["cct_1800_6500"] <= 6500
