from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from smart_lighting_ai_dali.db import SessionLocal
from smart_lighting_ai_dali.models import Decision, FeatureRow


EXPORT_COLUMNS = [
    "timestamp",
    "ambient_lux_mean",
    "ambient_lux_delta",
    "occupancy_rate",
    "weather_summary",
    "age_bucket",
    "impairment_enum",
    "intensity",
    "cct",
]


def export_csv(path: Path) -> None:
    with SessionLocal() as session:  # type: ignore[call-arg]
        rows = (
            session.query(FeatureRow, Decision)
            .outerjoin(Decision, Decision.feature_row_id == FeatureRow.id)
            .order_by(FeatureRow.window_end.desc())
            .all()
        )
        data = []
        for feature, decision in rows:
            data.append(
                {
                    "timestamp": feature.window_end.isoformat(),
                    "ambient_lux_mean": feature.ambient_lux_mean,
                    "ambient_lux_delta": feature.ambient_lux_delta,
                    "occupancy_rate": feature.occupancy_rate,
                    "weather_summary": feature.weather_summary,
                    "age_bucket": feature.age_bucket,
                    "impairment_enum": feature.impairment_enum,
                    "intensity": decision.intensity if decision else None,
                    "cct": decision.cct if decision else None,
                }
            )
        df = pd.DataFrame(data)
        if not df.empty:
            df = df[EXPORT_COLUMNS]
        df.to_csv(path, index=False)
        parquet_path = path.with_suffix(".parquet")
        df.to_parquet(parquet_path, index=False)
        print(f"Exported {len(df)} rows to {path} and {parquet_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", help="Output CSV path")
    args = parser.parse_args()
    export_csv(Path(args.output))
