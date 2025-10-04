"""CLI entry point for posting simulated weather observations."""

from __future__ import annotations

from smart_lighting_ai_dali.scripts.ingest_weather import ingest, parse_args


if __name__ == "__main__":
    args = parse_args()
    ingest(args.endpoint, args.interval, args.duration, args.seed)
