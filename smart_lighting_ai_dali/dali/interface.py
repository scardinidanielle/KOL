from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def clamp_intensity(intensity: int) -> int:
    return max(0, min(100, int(intensity)))


def clamp_cct(cct: int) -> int:
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
