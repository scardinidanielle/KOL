from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

try:  # pragma: no cover - import guard for optional dependency
    from openai import OpenAI, OpenAIError
except Exception:  # noqa: BLE001
    OpenAI = None  # type: ignore[assignment]

    class OpenAIError(Exception):
        """Fallback OpenAI error when the SDK is unavailable."""


from .config import get_settings
from .dali import clamp_cct, clamp_intensity

logger = logging.getLogger(__name__)


@dataclass
class FeatureWindow:
    payload: Dict[str, Any]
    timestamp: str


class AIController:
    def __init__(self, settings=None, client: OpenAI | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client
        if (
            self.client is None
            and self.settings.openai_api_key
            and OpenAI is not None
        ):
            self.client = OpenAI(api_key=self.settings.openai_api_key)

    def _build_payload(self, features: Iterable[FeatureWindow]) -> dict[str, Any]:
        payload = {
            "windows": [fw.payload for fw in features],
        }
        payload_json = json.dumps(payload)
        payload_size = len(payload_json.encode("utf-8"))
        if payload_size > self.settings.payload_cap_bytes:
            raise ValueError("Payload exceeds cap")
        if len(payload["windows"]) > self.settings.payload_batch_limit:
            raise ValueError("Too many feature windows")
        return payload

    def _call_openai(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.client:
            raise OpenAIError("OpenAI client not configured")
        response = self.client.responses.create(
            model="gpt-4.1-mini",
            temperature=0.2,
            reasoning={"effort": "medium"},
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a smart lighting controller optimizing comfort, "
                        "accessibility, and energy efficiency."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(payload),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "lighting_setpoint",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "intensity_0_100": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                            },
                            "cct_1800_6500": {
                                "type": "integer",
                                "minimum": 1800,
                                "maximum": 6500,
                            },
                            "reason": {"type": "string"},
                        },
                        "required": [
                            "intensity_0_100",
                            "cct_1800_6500",
                            "reason",
                        ],
                    },
                },
            },
        )
        text_payload: str | None = None

        if hasattr(response, "output_text"):
            text_payload = getattr(response, "output_text") or None

        if not text_payload:
            outputs = getattr(response, "output", None)
            if outputs:
                try:
                    first_output = outputs[0]
                except IndexError:
                    first_output = None
                if first_output is not None:
                    content_items = getattr(first_output, "content", None)
                    if content_items:
                        try:
                            first_item = content_items[0]
                        except IndexError:
                            first_item = None
                        if first_item is not None:
                            text_block = getattr(first_item, "text", None)
                            if isinstance(text_block, str):
                                text_payload = text_block or None
                            elif text_block is not None:
                                text_payload = getattr(text_block, "value", None) or None

        if not text_payload:
            raise OpenAIError("Invalid response")

        return json.loads(text_payload)

    def fallback(self, features: Iterable[FeatureWindow]) -> dict[str, Any]:
        windows = list(features)
        latest = windows[-1].payload if windows else {}
        ambient = latest.get("ambient_lux", 300)
        occupancy = latest.get("occupancy", 0)
        impairment = latest.get("impairment_enum", "none")
        weather = (latest.get("weather_summary") or "clear").lower()
        time_of_day = latest.get("time_of_day", "day")

        if occupancy < 0.5:
            intensity = 10
        else:
            base = 60 - int(ambient / 10)
            if impairment == "low_vision":
                base += 10
            elif impairment == "photosensitive":
                base -= 15
            if weather in {"overcast", "rain"}:
                base += 10
            if time_of_day in {"evening", "night"}:
                base -= 5
            intensity = max(20, base)

        if impairment == "photosensitive":
            cct = 3200
        elif time_of_day in {"morning"}:
            cct = 5000
        elif time_of_day in {"evening", "night"}:
            cct = 3000
        else:
            cct = 4000

        reason = "Fallback rules applied"
        return {
            "intensity_0_100": clamp_intensity(intensity),
            "cct_1800_6500": clamp_cct(cct),
            "reason": reason,
        }

    def compute_setpoint(self, features: List[FeatureWindow]) -> tuple[dict[str, Any], int]:
        payload = self._build_payload(features)
        payload_json = json.dumps(payload)
        payload_size = len(payload_json.encode("utf-8"))
        attempts = 0
        while attempts < 3:
            attempts += 1
            try:
                result = self._call_openai(payload)
                result["intensity_0_100"] = clamp_intensity(result["intensity_0_100"])
                result["cct_1800_6500"] = clamp_cct(result["cct_1800_6500"])
                return result, payload_size
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "OpenAI call failed, retrying",
                    extra={"error": str(exc), "attempt": attempts},
                )
                time.sleep(0.5 * attempts)
        logger.error("Falling back to rules controller")
        return self.fallback(features), payload_size


__all__ = ["AIController", "FeatureWindow"]
