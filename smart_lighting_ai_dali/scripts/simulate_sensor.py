"""Utility for sending deterministic sensor telemetry to the API."""

from __future__ import annotations

import argparse
import random
import time
from datetime import datetime
from typing import Iterator

import requests


def _iter_readings(rng: random.Random) -> Iterator[dict[str, float | int | str]]:
    """Yield pseudo-randomised sensor readings suitable for ingestion."""

    step = 0
    while True:
        base = 320 + 45 * rng.random()
        oscillation = 30 * (1 if step % 2 else -1)
        presence = 1 if rng.random() < 0.55 else 0
        ambient_lux = max(40.0, base + oscillation + presence * 60)
        yield {
            "ambient_lux": round(ambient_lux, 2),
            "presence": bool(presence),
            "timestamp": datetime.utcnow().isoformat(),
        }
        step += 1


def simulate(endpoint: str, interval: float, duration: float, seed: int | None) -> None:
    """Post sensor readings to the ingest endpoint at the desired cadence."""

    rng = random.Random(seed or 0)
    iterator = _iter_readings(rng)
    end_time = time.monotonic() + duration if duration > 0 else None
    idx = 0
    while True:
        reading = next(iterator)
        response = requests.post(endpoint, json=reading, timeout=5)
        response.raise_for_status()
        print(f"[{idx}] sent {reading} -> {response.json()}")
        idx += 1
        if end_time is None:
            time.sleep(interval)
            continue
        if time.monotonic() >= end_time:
            break
        time.sleep(interval)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--endpoint",
        default="http://localhost:8000/ingest/sensor",
        help="Sensor ingest endpoint (default: http://localhost:8000/ingest/sensor)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Interval in seconds between readings (default: 2.0)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Total duration in seconds to run the simulation (default: 30)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic output (default: 42)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    simulate(args.endpoint, args.interval, args.duration, args.seed)
