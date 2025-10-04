from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    Decision,
    FeatureRow,
    ManualOverride,
    RawSensorEvent,
    Telemetry,
    WeatherEvent,
)


def prune_old_data(session: Session) -> dict[str, int]:
    settings = get_settings()
    now = datetime.utcnow()
    counts = {
        "raw": 0,
        "features": 0,
        "decisions": 0,
        "telemetry": 0,
        "weather": 0,
        "overrides": 0,
    }

    raw_threshold = now - timedelta(days=settings.retention_raw_days)
    counts["raw"] = (
        session.query(RawSensorEvent)
        .filter(RawSensorEvent.created_at < raw_threshold)
        .delete()
    )

    feature_threshold = now - timedelta(days=settings.retention_feature_days)
    counts["features"] = (
        session.query(FeatureRow)
        .filter(FeatureRow.created_at < feature_threshold)
        .delete()
    )

    decision_threshold = now - timedelta(days=settings.retention_decision_days)
    counts["decisions"] = (
        session.query(Decision)
        .filter(Decision.decided_at < decision_threshold)
        .delete()
    )

    counts["telemetry"] = (
        session.query(Telemetry)
        .filter(Telemetry.recorded_at < decision_threshold)
        .delete()
    )
    counts["weather"] = (
        session.query(WeatherEvent)
        .filter(WeatherEvent.created_at < feature_threshold)
        .delete()
    )
    counts["overrides"] = (
        session.query(ManualOverride)
        .filter(ManualOverride.expires_at < raw_threshold)
        .delete()
    )
    session.commit()
    return counts


__all__ = ["prune_old_data"]
