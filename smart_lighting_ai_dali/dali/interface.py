from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

from ..config import get_settings

logger = logging.getLogger(__name__)


def clamp_intensity(intensity: int) -> int:
    """Clamp an intensity value to the valid 0-100 range."""

    return max(0, min(100, int(intensity)))


def clamp_cct(cct: int) -> int:
    """Clamp a correlated colour temperature to the valid DT8 range."""

    return max(1800, min(6500, int(cct)))


@dataclass
class DT8Command:
    """Represents a DALI DT8 command payload for tunable white luminaires."""

    address: int
    data: bytes


class DALIInterface(ABC):
    @abstractmethod
    def send_dt8(self, intensity: int, cct: int) -> None:
        """Send a DT8 command."""

    @abstractmethod
    def diagnostics(self) -> dict[str, str]:
        """Return diagnostics information."""

    def read_sensor(self) -> dict[str, int]:  # pragma: no cover - optional
        """Return a mock sensor reading if supported."""

        raise NotImplementedError


def dt8_warm_cool_to_bytes(cct: int) -> bytes:
    """Map CCT to a DT8 warm/cool command (simplified for tunable white)."""
    # DALI DT8 typically uses 16-bit data, scaled 0-65535 for temperature.
    # We'll map 1800-6500 K to that range.
    cct_clamped = clamp_cct(cct)
    scale = (cct_clamped - 1800) / (6500 - 1800)
    dali_value = int(scale * 65535)
    return dali_value.to_bytes(2, byteorder="big")


class TridonicUSBInterface(DALIInterface):
    """Stubbed implementation for Tridonic DALI USB interface."""

    def __init__(self) -> None:
        self._last_command: DT8Command | None = None

    def send_dt8(self, intensity: int, cct: int) -> None:
        intensity_clamped = clamp_intensity(intensity)
        cct_bytes = dt8_warm_cool_to_bytes(cct)
        payload = DT8Command(address=0xFF, data=intensity_clamped.to_bytes(1, "big") + cct_bytes)
        logger.info("Sending DT8 command", extra={
            "command": {
                "address": payload.address,
                "intensity": intensity_clamped,
                "cct": int.from_bytes(cct_bytes, "big"),
            }
        })
        self._last_command = payload
        time.sleep(0.05)  # simulate transmission delay

    def diagnostics(self) -> dict[str, str]:
        if self._last_command is None:
            return {"status": "idle"}
        return {
            "status": "ok",
            "last_intensity": str(self._last_command.data[0]),
            "last_cct_value": str(int.from_bytes(self._last_command.data[1:], "big")),
        }


class MockDALIInterface(DALIInterface):
    def __init__(self) -> None:
        self.sent_commands: list[DT8Command] = []

    def send_dt8(self, intensity: int, cct: int) -> None:
        intensity_clamped = clamp_intensity(intensity)
        cct_bytes = dt8_warm_cool_to_bytes(cct)
        command = DT8Command(address=0xFF, data=intensity_clamped.to_bytes(1, "big") + cct_bytes)
        logger.debug("Mock send DT8", extra={"command": command})
        self.sent_commands.append(command)

    def diagnostics(self) -> dict[str, str]:
        if not self.sent_commands:
            return {"status": "idle"}
        last = self.sent_commands[-1]
        return {
            "status": "ok",
            "last_intensity": str(last.data[0]),
            "last_cct_value": str(int.from_bytes(last.data[1:], "big")),
            "commands_sent": str(len(self.sent_commands)),
        }


class MockDALIController(DALIInterface):
    """In-memory mock controller mirroring basic Tridonic USB DT8 behaviour."""

    def __init__(
        self,
        settings=None,
        *,
        seed: int | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._rng = random.Random(seed or 0)
        self._clock = 0.0
        self._last_update_tick = -float(self.settings.min_update_interval_seconds)
        self._state: Dict[str, Any] = {
            "intensity": 0,
            "cct": 4000,
            "timestamp": self._clock,
        }
        self._history: list[Dict[str, Any]] = []
        self._last_response: Dict[str, Any] | None = None

    def _tick(self, seconds: float = 1.0) -> float:
        self._clock = round(self._clock + seconds, 3)
        return self._clock

    def _limit_delta(self, current: int, target: int, limit: float) -> int:
        delta = target - current
        if abs(delta) <= limit:
            return int(target)
        step = limit if delta > 0 else -limit
        return int(current + step)

    def set_light(self, intensity: int, cct: int) -> dict[str, Any]:
        """Apply a light state while respecting anti-flicker bounds."""

        intensity = clamp_intensity(intensity)
        cct = clamp_cct(cct)
        elapsed = self._clock - self._last_update_tick
        applied = True
        if elapsed < self.settings.min_update_interval_seconds:
            applied = False
            intensity = int(self._state["intensity"])
            cct = int(self._state["cct"])
        else:
            max_delta = (
                self.settings.anti_flicker_delta_per_second * max(elapsed, 1.0)
            )
            new_intensity = self._limit_delta(
                int(self._state["intensity"]),
                intensity,
                max_delta,
            )
            new_cct = self._limit_delta(
                int(self._state["cct"]),
                cct,
                max_delta * 20,
            )
            applied = (
                new_intensity != self._state["intensity"]
                or new_cct != self._state["cct"]
            )
            self._state["intensity"] = new_intensity
            self._state["cct"] = new_cct
            self._last_update_tick = self._clock

        timestamp = self._tick()
        self._state["timestamp"] = timestamp
        snapshot = dict(self._state)
        self._history.append(snapshot)
        logger.info(
            "Mock DALI applied setpoint",
            extra={"state": snapshot, "applied": applied},
        )
        self._last_response = {"status": "ok", "applied": applied, "state": snapshot}
        return self._last_response

    def send_dt8(self, intensity: int, cct: int) -> None:
        self.set_light(intensity, cct)

    def read_sensor(self) -> dict[str, int]:
        """Return a deterministic pseudo-random sensor observation."""

        timestamp = self._tick()
        baseline = max(80, 600 - int(self._state["intensity"]) * 3)
        lux = max(10, int(baseline + self._rng.randint(-20, 20)))
        presence_threshold = 0.3 + (int(self._state["intensity"]) / 250.0)
        presence = 1 if self._rng.random() < min(presence_threshold, 0.9) else 0
        reading = {"lux": lux, "presence": presence}
        logger.debug(
            "Mock sensor reading",
            extra={"reading": {**reading, "timestamp": timestamp}},
        )
        return reading

    def diagnostics(self) -> dict[str, str]:
        state = self._last_response["state"] if self._last_response else self._state
        return {
            "status": "mock",
            "mode": "mock",
            "intensity": str(int(state["intensity"])),
            "cct": str(int(state["cct"])),
            "clock": f"{self._clock:.3f}",
        }
