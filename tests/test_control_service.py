from __future__ import annotations

from smart_lighting_ai_dali.control_service import ControlService
from smart_lighting_ai_dali.dali import MockDALIInterface, dt8_warm_cool_to_bytes
from smart_lighting_ai_dali.models import ManualOverride


def test_dt8_mapping():
    data = dt8_warm_cool_to_bytes(4000)
    assert isinstance(data, bytes)
    assert len(data) == 2


def test_control_clamps_values(db_session):
    service = ControlService(MockDALIInterface())
    decision = service.apply(
        db_session,
        intensity=150,
        cct=1000,
        reason="test",
        source="test",
    )
    assert 0 <= decision.intensity <= 100
    assert decision.cct >= 1800


def test_manual_override_applies(db_session):
    service = ControlService(MockDALIInterface())
    # create override
    service.apply(
        db_session,
        intensity=60,
        cct=3000,
        reason="override",
        source="manual",
        manual_override=True,
        override_minutes=30,
    )
    override = db_session.query(ManualOverride).first()
    assert override is not None
    decision = service.apply(
        db_session,
        intensity=10,
        cct=6500,
        reason="ai",
        source="ai",
    )
    assert decision.intensity == override.intensity
    assert decision.manual_override_applied


def test_anti_flicker_limits(db_session):
    service = ControlService(MockDALIInterface())
    first = service.apply(
        db_session,
        intensity=10,
        cct=2000,
        reason="base",
        source="ai",
    )
    second = service.apply(
        db_session,
        intensity=100,
        cct=6500,
        reason="jump",
        source="ai",
    )
    max_delta = (
        service.settings.anti_flicker_delta_per_second
        * service.settings.min_update_interval_seconds
    )
    assert abs(second.intensity - first.intensity) <= max_delta
