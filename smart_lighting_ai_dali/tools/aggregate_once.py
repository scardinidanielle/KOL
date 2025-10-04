from __future__ import annotations

import sys

from ..config import get_settings
from ..db import session_scope
from ..feature_engineering import aggregate_features


def main() -> int:
    """Aggregate a single set of features and report the outcome."""
    settings = get_settings()
    try:
        with session_scope() as session:
            feature_row = aggregate_features(session, settings.feature_window_minutes)
    except Exception as exc:  # noqa: BLE001
        print(f"Aggregation failed: {exc}", file=sys.stderr)
        return 1

    if feature_row is None:
        print("No new feature row created.")
        return 0

    print(
        "Created feature row",
        f"id={feature_row.id}",
        f"window_start={feature_row.window_start.isoformat()}",
        f"window_end={feature_row.window_end.isoformat()}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
