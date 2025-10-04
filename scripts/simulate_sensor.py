"""CLI entry point for sensor simulation in development mode."""

from __future__ import annotations

from smart_lighting_ai_dali.scripts.simulate_sensor import parse_args, simulate


if __name__ == "__main__":
    args = parse_args()
    simulate(args.endpoint, args.interval, args.duration, args.seed)
