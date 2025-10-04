from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from statistics import mean
from typing import List, Tuple

from cryptography.fernet import Fernet
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from .config import get_settings
from .models import (
    FeatureRow,
    ManualOverride,
    PersonalProfile,
    RawSensorEvent,
    WeatherEvent,
)

logger = logging.getLogger(__name__)


def _load_profile_features(session: Session, settings) -> dict[str, str | None]:
    profile = (
        session.query(PersonalProfile)
        .order_by(desc(PersonalProfile.created_at))
        .first()
    )
    if not profile:
        return {
            "age_bucket": None,
            "sex_enum": None,
            "impairment_enum": None,
            "user_state": "default",
            "chronotype_enum": None,
        }
    fernet = Fernet(settings.fernet_key)
    decrypted = fernet.decrypt(profile.encrypted_payload.encode("utf-8"))
    data = json.loads(decrypted)
    age = data.get("age", 35)
    if age < 25:
        age_bucket = "18-24"
    elif age < 45:
        age_bucket = "25-44"
    elif age < 65:
        age_bucket = "45-64"
    else:
        age_bucket = "65+"
    schedules = data.get("schedules", {})
    now = datetime.utcnow()
    user_state = schedules.get(now.strftime("%A"), "default")
    return {
        "age_bucket": age_bucket,
        "sex_enum": data.get("sex"),
        "impairment_enum": data.get("visual_impairment"),
        "user_state": user_state,
        "chronotype_enum": data.get("chronotype"),
    }


def _time_bucket(ts: datetime) -> Tuple[str, str]:
    hour = ts.hour
    if 6 <= hour < 12:
        tod = "morning"
    elif 12 <= hour < 17:
        tod = "day"
    elif 17 <= hour < 21:
        tod = "evening"
    else:
        tod = "night"
    return tod, ts.strftime("%A")


def aggregate_features(session: Session, window_minutes: int | None = None) -> FeatureRow | None:
    settings = get_settings()
    window_minutes = window_minutes or settings.feature_window_minutes
    window_end = datetime.utcnow()
    window_start = window_end - timedelta(minutes=window_minutes)

    events = (
        session.query(RawSensorEvent)
        .filter(RawSensorEvent.timestamp >= window_start)
        .order_by(asc(RawSensorEvent.timestamp))
        .all()
    )
    if not events:
        logger.debug("No sensor events available for feature aggregation")
        return None

    lux_values = [event.ambient_lux for event in events]
    occupancy_values = [1 if event.presence else 0 for event in events]
    ambient_mean = float(mean(lux_values))
    ambient_max = float(max(lux_values))
    ambient_min = float(min(lux_values))
    ambient_delta = (
        float(lux_values[-1] - lux_values[0]) if len(lux_values) > 1 else 0.0
    )
    occupancy_rate = float(mean(occupancy_values))
    occupancy_last = bool(events[-1].presence)

    weather = session.query(WeatherEvent).order_by(desc(WeatherEvent.timestamp)).first()

    profile_features = _load_profile_features(session, settings)

    time_of_day, day_of_week = _time_bucket(window_end)

    payload = {
        **profile_features,
        "ambient_lux": ambient_mean,
        "occupancy": occupancy_rate,
        "weather_summary": weather.weather_summary if weather else None,
        "time_of_day": time_of_day,
        "day_of_week": day_of_week,
    }
    payload_bytes = len(json.dumps(payload).encode("utf-8"))

    feature_row = FeatureRow(
        window_start=window_start,
        window_end=window_end,
        ambient_lux_mean=ambient_mean,
        ambient_lux_max=ambient_max,
        ambient_lux_min=ambient_min,
        ambient_lux_delta=ambient_delta,
        occupancy_rate=occupancy_rate,
        occupancy_last=occupancy_last,
        weather_summary=weather.weather_summary if weather else None,
        age_bucket=profile_features.get("age_bucket"),
        sex_enum=profile_features.get("sex_enum"),
        impairment_enum=profile_features.get("impairment_enum"),
        user_state=profile_features.get("user_state"),
        chronotype_enum=profile_features.get("chronotype_enum"),
        time_of_day=time_of_day,
        day_of_week=day_of_week,
        payload_size_estimate=payload_bytes,
    )
    session.add(feature_row)
    session.commit()
    session.refresh(feature_row)
    logger.info(
        "Feature row created",
        extra={"feature_id": feature_row.id, "payload_bytes": payload_bytes},
    )
    return feature_row


def prepare_feature_windows(
    session: Session,
    rows: int | None = None,
) -> List[dict[str, str | float | None]]:
    settings = get_settings()
    rows = rows or settings.feature_history_rows
    query = (
        session.query(FeatureRow)
        .order_by(desc(FeatureRow.created_at))
        .limit(rows)
    )
    feature_rows = list(reversed(query.all()))
    windows: List[dict[str, str | float | None]] = []
    for row in feature_rows:
        payload = {
            "age_bucket": row.age_bucket,
            "sex_enum": row.sex_enum,
            "impairment_enum": row.impairment_enum,
            "user_state": row.user_state,
            "chronotype_enum": row.chronotype_enum,
            "ambient_lux": row.ambient_lux_mean,
            "occupancy": row.occupancy_rate,
            "weather_summary": row.weather_summary,
            "time_of_day": row.time_of_day,
            "day_of_week": row.day_of_week,
        }
        windows.append(payload)
    return windows


def get_active_override(session: Session) -> ManualOverride | None:
    now = datetime.utcnow()
    override = (
        session.query(ManualOverride)
        .filter(
            ManualOverride.active.is_(True),
            ManualOverride.expires_at > now,
        )
        .order_by(desc(ManualOverride.expires_at))
        .first()
    )
    if override is None:
        return None
    return override


__all__ = [
    "aggregate_features",
    "prepare_feature_windows",
    "get_active_override",
]
