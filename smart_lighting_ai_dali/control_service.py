from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .config import get_settings
from .dali import DALIInterface, clamp_cct, clamp_intensity
from .feature_engineering import get_active_override
from .models import Decision, FeatureRow, ManualOverride, Telemetry

logger = logging.getLogger(__name__)


class ControlService:
    def __init__(self, dali: DALIInterface, settings=None) -> None:
        self.dali = dali
        self.settings = settings or get_settings()

    def _apply_anti_flicker(
        self,
        session: Session,
        intensity: int,
        cct: int,
        *,
        supports_cct: bool = True,
    ) -> tuple[int, int]:
        latest = (
            session.query(Decision)
            .order_by(Decision.decided_at.desc())
            .first()
        )
        if not latest:
            return intensity, cct
        elapsed = (datetime.utcnow() - latest.decided_at).total_seconds()
        if elapsed < self.settings.min_update_interval_seconds:
            logger.info(
                "Skipping update due to min interval",
                extra={"elapsed": elapsed},
            )
            return latest.intensity, latest.cct
        max_delta = (
            self.settings.anti_flicker_delta_per_second * max(elapsed, 1)
        )
        if abs(intensity - latest.intensity) > max_delta:
            step = max_delta if intensity > latest.intensity else -max_delta
            intensity = latest.intensity + int(step)
        if not supports_cct:
            # Basic DALI mode retains the most recent colour temperature.
            cct = latest.cct
        elif abs(cct - latest.cct) > max_delta * 20:  # allow larger delta for cct scaling
            step_cct = (
                max_delta * 20 if cct > latest.cct else -max_delta * 20
            )
            cct = latest.cct + int(step_cct)
        return intensity, cct

    def apply(
        self,
        session: Session,
        *,
        intensity: int,
        cct: int,
        reason: str,
        source: str,
        feature_row: FeatureRow | None = None,
        manual_override: bool = False,
        override_minutes: int | None = None,
    ) -> Decision:
        intensity = clamp_intensity(intensity)
        cct = clamp_cct(cct)

        if manual_override and override_minutes:
            expires = datetime.utcnow() + timedelta(minutes=override_minutes)
            override = ManualOverride(
                intensity=intensity,
                cct=cct,
                reason=reason,
                created_at=datetime.utcnow(),
                expires_at=expires,
                active=True,
            )
            session.add(override)
            session.commit()
            logger.info(
                "Manual override stored",
                extra={"expires_at": expires.isoformat()},
            )

        active_override = get_active_override(session)
        override_applied = False
        if active_override:
            intensity = active_override.intensity
            cct = active_override.cct
            reason = active_override.reason or reason
            override_applied = True

        supports_cct = bool(getattr(self.dali, "supports_cct", True))
        if not supports_cct:
            logger.info(
                "Basic DALI mode active – retaining previous CCT value",
                extra={"requested_cct": cct},
            )
        intensity, cct = self._apply_anti_flicker(
            session,
            intensity,
            cct,
            supports_cct=supports_cct,
        )
        self.dali.send_dt8(intensity, cct)
        energy_saving = max(0.0, (100 - intensity) / 100.0)
        decision = Decision(
            intensity=intensity,
            cct=cct,
            reason=reason,
            payload_bytes=0,
            source=source,
            energy_saving_estimate=energy_saving,
            feature_row_id=feature_row.id if feature_row else None,
            manual_override_applied=override_applied,
        )
        session.add(decision)
        session.add(
            Telemetry(
                metric="energy_saving_estimate",
                value=energy_saving,
                detail=f"intensity={intensity}",
            )
        )
        session.commit()
        session.refresh(decision)
        return decision


__all__ = ["ControlService"]
