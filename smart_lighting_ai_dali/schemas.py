from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field, field_validator, model_validator


class SensorIngest(BaseModel):
    ambient_lux: float = Field(..., ge=0, le=1000)
    presence: bool
    timestamp: datetime | None = None


class WeatherIngest(BaseModel):
    weather_summary: str
    temperature_c: float | None = None
    sunrise: datetime | None = None
    sunset: datetime | None = None
    timestamp: datetime | None = None


class PredictRequest(BaseModel):
    window_rows: int | None = Field(default=None, ge=1, le=3)


class AISetpoint(BaseModel):
    intensity_0_100: int = Field(..., ge=0, le=100)
    cct_1800_6500: int = Field(..., ge=1800, le=6500)
    reason: str


class ControlRequest(BaseModel):
    intensity: int = Field(..., ge=0, le=100)
    cct: int = Field(..., ge=1800, le=6500)
    reason: str = Field("ai")
    source: str = Field("ai")
    manual_override: bool = False
    override_minutes: int | None = Field(default=None, ge=5, le=180)

    @model_validator(mode="after")
    def validate_manual_override(self) -> "ControlRequest":
        if self.manual_override and self.override_minutes is None:
            raise ValueError("override_minutes is required when manual_override is true")
        return self


class ControlResponse(BaseModel):
    applied: bool
    intensity: int
    cct: int
    reason: str
    manual_override_applied: bool


class TelemetryItem(BaseModel):
    decided_at: datetime
    intensity: int
    cct: int
    reason: str
    source: str
    energy_saving_estimate: float | None


class PaginatedTelemetry(BaseModel):
    items: List[TelemetryItem]
    next_offset: int | None
    limit: int


class ManualOverrideStatus(BaseModel):
    active: bool
    expires_at: datetime | None
    intensity: int | None
    cct: int | None
    reason: str | None


class HealthStatus(BaseModel):
    status: str
    database: str
    dali: str
    scheduler: str


class FeaturePayload(BaseModel):
    age_bucket: str | None
    sex_enum: str | None
    impairment_enum: str | None
    user_state: str | None
    chronotype_enum: str | None
    ambient_lux: float
    occupancy: float
    weather_summary: str | None
    time_of_day: str
    day_of_week: str


class PredictResponse(BaseModel):
    setpoint: AISetpoint
    payload_bytes: int
    features_used: int


class ProfileSubmission(BaseModel):
    user_id: str = Field(..., min_length=1)
    consent: bool = True
    age: int | None = Field(default=None, ge=0, le=120)
    sex: str | None = None
    visual_impairment: str | None = None
    chronotype: str | None = None
    schedules: dict[str, str] = Field(default_factory=dict)
    preferences: dict[str, str] = Field(default_factory=dict)

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("user_id cannot be blank")
        return value


__all__ = [
    "SensorIngest",
    "WeatherIngest",
    "PredictRequest",
    "AISetpoint",
    "ControlRequest",
    "ControlResponse",
    "TelemetryItem",
    "PaginatedTelemetry",
    "ManualOverrideStatus",
    "HealthStatus",
    "FeaturePayload",
    "PredictResponse",
    "ProfileSubmission",
]
