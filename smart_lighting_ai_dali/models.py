from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .db import Base


class RawSensorEvent(Base):
    __tablename__ = "raw_sensor_events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True, default=datetime.utcnow)
    ambient_lux = Column(Float, nullable=False)
    presence = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class WeatherEvent(Base):
    __tablename__ = "weather_events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True, default=datetime.utcnow)
    weather_summary = Column(String(64), nullable=False)
    temperature_c = Column(Float, nullable=True)
    sunrise = Column(DateTime, nullable=True)
    sunset = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PersonalProfile(Base):
    __tablename__ = "personal_profiles"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(String(64), unique=True, nullable=False)
    encrypted_payload = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ParticipantProfile(Base):
    __tablename__ = "participant_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), unique=True, nullable=False)
    encrypted_payload = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class FeatureRow(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True, index=True)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)
    ambient_lux_mean = Column(Float, nullable=False)
    ambient_lux_max = Column(Float, nullable=False)
    ambient_lux_min = Column(Float, nullable=False)
    ambient_lux_delta = Column(Float, nullable=False)
    occupancy_rate = Column(Float, nullable=False)
    occupancy_last = Column(Boolean, nullable=False)
    weather_summary = Column(String(64), nullable=True)
    age_bucket = Column(String(32), nullable=True)
    sex_enum = Column(String(16), nullable=True)
    impairment_enum = Column(String(32), nullable=True)
    user_state = Column(String(32), nullable=True)
    chronotype_enum = Column(String(32), nullable=True)
    time_of_day = Column(String(16), nullable=False)
    day_of_week = Column(String(16), nullable=False)
    payload_size_estimate = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    decisions = relationship("Decision", back_populates="feature_row")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, index=True)
    decided_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    intensity = Column(Integer, nullable=False)
    cct = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    payload_bytes = Column(Integer, nullable=True)
    source = Column(String(32), nullable=False)
    energy_saving_estimate = Column(Float, nullable=True)
    feature_row_id = Column(Integer, ForeignKey("features.id"), nullable=True)
    manual_override_applied = Column(Boolean, default=False, nullable=False)

    feature_row = relationship("FeatureRow", back_populates="decisions")


class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, index=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    metric = Column(String(64), nullable=False)
    value = Column(Float, nullable=True)
    detail = Column(Text, nullable=True)


class ManualOverride(Base):
    __tablename__ = "manual_overrides"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    intensity = Column(Integer, nullable=False)
    cct = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False)


__all__ = [
    "RawSensorEvent",
    "WeatherEvent",
    "PersonalProfile",
    "ParticipantProfile",
    "FeatureRow",
    "Decision",
    "Telemetry",
    "ManualOverride",
]
