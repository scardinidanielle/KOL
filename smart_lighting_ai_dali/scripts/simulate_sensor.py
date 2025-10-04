from __future__ import annotations

import argparse
import csv
from datetime import datetime

import requests


def simulate(endpoint: str, csv_path: str) -> None:
    with open(csv_path, "r", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            timestamp = row.get("timestamp") or datetime.utcnow().isoformat()
            payload = {
                "ambient_lux": float(row["ambient_lux"]),
                "presence": bool(int(row["presence"])),
                "timestamp": timestamp,
            }
            response = requests.post(endpoint, json=payload, timeout=5)
            response.raise_for_status()
            print("sent", payload, "->", response.json())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "endpoint",
        help="Sensor ingest endpoint, e.g., http://localhost:8000/ingest/sensor",
    )
    parser.add_argument(
        "csv",
        help="CSV file with ambient_lux,presence[,timestamp]",
    )
    args = parser.parse_args()
    simulate(args.endpoint, args.csv)
