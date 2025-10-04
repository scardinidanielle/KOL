"""Emit periodic weather observations to the local API."""

from __future__ import annotations

import argparse
import itertools
import random
import time
from datetime import datetime, timedelta
from typing import Iterator

import requests

_WEATHER_PRESETS = (
    {"weather_summary": "Clear", "temperature_c": 18.5},
    {"weather_summary": "Overcast", "temperature_c": 16.0},
    {"weather_summary": "Rain", "temperature_c": 14.5},
    {"weather_summary": "Partly Cloudy", "temperature_c": 17.2},
)


def _iter_weather(rng: random.Random) -> Iterator[dict[str, str | float]]:
    """Yield preset weather observations with slight deterministic variance."""

    base_time = datetime.utcnow()
    for idx, preset in enumerate(itertools.cycle(_WEATHER_PRESETS)):
        jitter = rng.uniform(-0.5, 0.5)
        timestamp = base_time + timedelta(minutes=idx * 10)
        sunrise = timestamp.replace(hour=6, minute=15, second=0, microsecond=0)
        sunset = timestamp.replace(hour=18, minute=45, second=0, microsecond=0)
        yield {
            "weather_summary": preset["weather_summary"],
            "temperature_c": round(preset["temperature_c"] + jitter, 1),
            "sunrise": sunrise.isoformat(),
            "sunset": sunset.isoformat(),
            "timestamp": timestamp.isoformat(),
        }


def ingest(endpoint: str, interval: float, duration: float, seed: int | None) -> None:
    """Post simulated weather data to the ingest endpoint."""

    rng = random.Random(seed or 0)
    iterator = _iter_weather(rng)
    end_time = time.monotonic() + duration if duration > 0 else None
    idx = 0
    while True:
        payload = next(iterator)
        response = requests.post(endpoint, json=payload, timeout=5)
        response.raise_for_status()
        print(f"[{idx}] weather {payload} -> {response.json()}")
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
        default="http://localhost:8000/ingest/weather",
        help="Weather ingest endpoint (default: http://localhost:8000/ingest/weather)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=60.0,
        help="Interval in seconds between posts (default: 60)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=300.0,
        help="Total duration in seconds to run the ingestion (default: 300)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Random seed for deterministic jitter (default: 7)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ingest(args.endpoint, args.interval, args.duration, args.seed)
