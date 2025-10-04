from __future__ import annotations

import argparse
import json
from datetime import datetime

import requests


def ingest(api_endpoint: str, json_path: str) -> None:
    with open(json_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    payload = {
        "weather_summary": data["weather_summary"],
        "temperature_c": data.get("temperature_c"),
        "sunrise": data.get("sunrise") or datetime.utcnow().isoformat(),
        "sunset": data.get("sunset") or datetime.utcnow().isoformat(),
        "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
    }
    response = requests.post(api_endpoint, json=payload, timeout=5)
    response.raise_for_status()
    print("weather ingested", response.json())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("endpoint", help="Weather ingest endpoint")
    parser.add_argument("json", help="JSON file with weather data")
    args = parser.parse_args()
    ingest(args.endpoint, args.json)
