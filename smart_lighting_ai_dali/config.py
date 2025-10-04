from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field("smart-lighting-ai-dali")
    db_url: str = Field("sqlite:///./smart_lighting.db")
    openai_api_key: str | None = Field(default=None)
    openai_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_MODEL", "openai_model"),
    )
    openai_enable_reasoning: bool = Field(False)
    admin_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ADMIN_TOKEN", "admin_token"),
    )
    weather_api_key: str | None = Field(default=None)
    fernet_key: str = Field(...)

    feature_window_minutes: int = Field(5)
    feature_history_rows: int = Field(3)
    payload_cap_bytes: int = Field(2048)
    payload_batch_limit: int = Field(3)

    anti_flicker_delta_per_second: int = Field(20)
    min_update_interval_seconds: int = Field(5)

    use_mock_dali: bool = Field(False, validation_alias="USE_MOCK_DALI")

    quiet_hours_start: int = Field(22)
    quiet_hours_end: int = Field(6)

    glare_overcast_threshold: int = Field(600)
    glare_sunny_threshold: int = Field(800)

    rate_limit_requests: int = Field(60)
    rate_limit_window_seconds: int = Field(60)

    retention_raw_days: int = Field(30)
    retention_feature_days: int = Field(90)
    retention_decision_days: int = Field(180)
    retention_override_grace_seconds: int = Field(60)

    @field_validator("feature_history_rows")
    @classmethod
    def validate_history_rows(cls, value: int) -> int:
        if value < 1 or value > 3:
            raise ValueError("feature_history_rows must be between 1 and 3")
        return value

    @field_validator("payload_cap_bytes")
    @classmethod
    def validate_payload_cap(cls, value: int) -> int:
        if value < 512:
            raise ValueError("payload_cap_bytes must be >= 512")
        return value

    @property
    def quiet_hours_range(self) -> List[int]:
        return [self.quiet_hours_start, self.quiet_hours_end]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]
