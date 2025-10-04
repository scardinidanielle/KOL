from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .control_service import ControlService
from .dali import MockDALIInterface, TridonicUSBInterface
from .db import Base, engine, get_db
from .feature_engineering import aggregate_features, prepare_feature_windows
from .logging_config import configure_logging
from .models import Decision, FeatureRow, RawSensorEvent, WeatherEvent
from .openai_client import AIController, FeatureWindow
from .rate_limit import InMemoryRateLimiter
from .retention import prune_old_data
from .schemas import (
    ControlRequest,
    ControlResponse,
    HealthStatus,
    PaginatedTelemetry,
    PredictRequest,
    PredictResponse,
    SensorIngest,
    TelemetryItem,
    WeatherIngest,
)

logger = logging.getLogger(__name__)

_LOGGING_CONFIGURED = False


def create_app(settings: Optional[Settings] = None, *, use_mock_dali: bool = True) -> FastAPI:
    global _LOGGING_CONFIGURED

    settings = settings or get_settings()
    if not _LOGGING_CONFIGURED:
        configure_logging()
        _LOGGING_CONFIGURED = True
    Base.metadata.create_all(bind=engine)
    dali = MockDALIInterface() if use_mock_dali else TridonicUSBInterface()
    control_service = ControlService(dali=dali, settings=settings)
    ai_controller = AIController(settings=settings, client=None)
    rate_limiter = InMemoryRateLimiter()
    scheduler = BackgroundScheduler()

    app = FastAPI(title=settings.app_name)
    app.state.scheduler = scheduler
    app.state.control_service = control_service
    app.state.ai_controller = ai_controller
    app.state.rate_limiter = rate_limiter
    app.state.logging_configured = True

    def feature_job() -> None:
        with engine.begin() as connection:
            session = Session(bind=connection)
            try:
                aggregate_features(session, settings.feature_window_minutes)
            finally:
                session.close()

    def retention_job() -> None:
        with engine.begin() as connection:
            session = Session(bind=connection)
            try:
                prune_old_data(session)
            finally:
                session.close()

    if not scheduler.running:
        scheduler.add_job(
            feature_job,
            "interval",
            minutes=settings.feature_window_minutes,
            id="feature_job",
        )
        scheduler.add_job(
            retention_job,
            "cron",
            hour=0,
            id="retention_job",
        )
        scheduler.start()

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):  # noqa: ANN001
        rate_limiter.check(request)
        response = await call_next(request)
        return response

    @app.post("/ingest/sensor", status_code=201)
    def ingest_sensor(payload: SensorIngest, db: Session = Depends(get_db)):
        event = RawSensorEvent(
            ambient_lux=payload.ambient_lux,
            presence=payload.presence,
            timestamp=payload.timestamp or datetime.utcnow(),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return {"id": event.id}

    @app.post("/ingest/weather", status_code=201)
    def ingest_weather(payload: WeatherIngest, db: Session = Depends(get_db)):
        event = WeatherEvent(
            weather_summary=payload.weather_summary,
            temperature_c=payload.temperature_c,
            sunrise=payload.sunrise,
            sunset=payload.sunset,
            timestamp=payload.timestamp or datetime.utcnow(),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return {"id": event.id}

    @app.post("/predict", response_model=PredictResponse)
    def predict(request: PredictRequest, db: Session = Depends(get_db)):
        windows = prepare_feature_windows(db, rows=request.window_rows)
        if not windows:
            return JSONResponse(status_code=400, content={"detail": "No features available"})
        feature_windows = [
            FeatureWindow(payload=window, timestamp=datetime.utcnow().isoformat())
            for window in windows
        ]
        try:
            setpoint, payload_size = ai_controller.compute_setpoint(feature_windows)
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"detail": str(exc)},
            )
        feature_row = (
            db.query(FeatureRow)
            .order_by(FeatureRow.created_at.desc())
            .first()
        )
        decision = Decision(
            intensity=setpoint["intensity_0_100"],
            cct=setpoint["cct_1800_6500"],
            reason=setpoint["reason"],
            payload_bytes=payload_size,
            source="ai",
            feature_row_id=feature_row.id if feature_row else None,
            manual_override_applied=False,
        )
        db.add(decision)
        db.commit()
        return PredictResponse(
            setpoint=setpoint,
            payload_bytes=payload_size,
            features_used=len(windows),
        )

    @app.post("/control", response_model=ControlResponse)
    def control(payload: ControlRequest, db: Session = Depends(get_db)):
        feature_row = (
            db.query(FeatureRow)
            .order_by(FeatureRow.created_at.desc())
            .first()
        )
        decision = control_service.apply(
            db,
            intensity=payload.intensity,
            cct=payload.cct,
            reason=payload.reason,
            source=payload.source,
            feature_row=feature_row,
            manual_override=payload.manual_override,
            override_minutes=payload.override_minutes,
        )
        return ControlResponse(
            applied=True,
            intensity=decision.intensity,
            cct=decision.cct,
            reason=decision.reason,
            manual_override_applied=decision.manual_override_applied,
        )

    @app.get("/telemetry", response_model=PaginatedTelemetry)
    def telemetry(limit: int = 25, offset: int = 0, db: Session = Depends(get_db)):
        query = db.query(Decision).order_by(Decision.decided_at.desc())
        items = query.offset(offset).limit(limit).all()
        total = query.count()
        next_offset = offset + limit if offset + limit < total else None
        payload = [
            TelemetryItem(
                decided_at=item.decided_at,
                intensity=item.intensity,
                cct=item.cct,
                reason=item.reason,
                source=item.source,
                energy_saving_estimate=item.energy_saving_estimate,
            )
            for item in items
        ]
        return PaginatedTelemetry(
            items=payload,
            next_offset=next_offset,
            limit=limit,
        )

    @app.get("/healthz", response_model=HealthStatus)
    def healthz(db: Session = Depends(get_db)):
        try:
            db.execute("SELECT 1")
            db_status = "ok"
        except Exception as exc:  # noqa: BLE001
            logger.error("Database health check failed", extra={"error": str(exc)})
            db_status = "error"
        dali_status = control_service.dali.diagnostics().get("status", "unknown")
        scheduler_status = "running" if scheduler.running else "stopped"
        return HealthStatus(
            status="ok",
            database=db_status,
            dali=dali_status,
            scheduler=scheduler_status,
        )

    @app.on_event("shutdown")
    def shutdown_event() -> None:
        try:
            scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass

    return app


app = create_app()


__all__ = ["create_app", "app"]
