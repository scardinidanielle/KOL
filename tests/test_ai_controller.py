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
                class _TextBlock:
                    def __init__(self, value):
                        self.value = value

                class _ContentBlock:
                    def __init__(self, value):
                        self.text = _TextBlock(value)

                class _OutputBlock:
                    def __init__(self, value):
                        self.content = [_ContentBlock(value)]

                self.output = [_OutputBlock(json.dumps(payload))]

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


def test_openai_model_and_reasoning_usage():
    from smart_lighting_ai_dali.config import get_settings

    base_settings = get_settings()
    custom_settings = base_settings.model_copy(
        update={
            "openai_model": "gpt-custom-model",
            "openai_enable_reasoning": False,
        }
    )

    class FakeClient:
        def __init__(self):
            self.responses = self
            self.last_kwargs: dict[str, object] | None = None

        def create(self, **kwargs):  # noqa: ANN003
            self.last_kwargs = kwargs

            class _Response:
                output_text = json.dumps(
                    {
                        "intensity_0_100": 50,
                        "cct_1800_6500": 3500,
                        "reason": "test",
                    }
                )

            return _Response()

    fake_client = FakeClient()
    controller = AIController(settings=custom_settings, client=fake_client)
    controller._call_openai({"windows": []})

    assert fake_client.last_kwargs is not None
    assert fake_client.last_kwargs["model"] == "gpt-custom-model"
    assert "reasoning" not in fake_client.last_kwargs
