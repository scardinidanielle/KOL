from __future__ import annotations

import json
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .control_service import ControlService
from .dali import MockDALIController, TridonicUSBInterface
from .db import Base, engine, get_db
from .feature_engineering import aggregate_features, prepare_feature_windows
from .logging_config import configure_logging
from .models import (
    Decision,
    FeatureRow,
    ParticipantProfile,
    RawSensorEvent,
    WeatherEvent,
)
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
    ProfileSubmission,
    SensorIngest,
    TelemetryItem,
    WeatherIngest,
)

logger = logging.getLogger(__name__)

_LOGGING_CONFIGURED = False


def create_app(
    settings: Optional[Settings] = None,
    *,
    use_mock_dali: bool | None = None,
) -> FastAPI:
    global _LOGGING_CONFIGURED

    settings = settings or get_settings()
    if not _LOGGING_CONFIGURED:
        configure_logging()
        _LOGGING_CONFIGURED = True
    Base.metadata.create_all(bind=engine)
    if use_mock_dali is None:
        use_mock_dali = settings.use_mock_dali
    dali = (
        MockDALIController(settings=settings)
        if use_mock_dali
        else TridonicUSBInterface(settings=settings)
    )
    control_service = ControlService(dali=dali, settings=settings)
    ai_controller = AIController(settings=settings, client=None)
    rate_limiter = InMemoryRateLimiter()
    scheduler = BackgroundScheduler()
    fernet = Fernet(settings.fernet_key)

    def serialize_sensor_event(event: RawSensorEvent | None) -> dict[str, Any] | None:
        if not event:
            return None
        return {
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "ambient_lux": event.ambient_lux,
            "presence": bool(event.presence),
        }

    def serialize_decision(decision: Decision | None) -> dict[str, Any] | None:
        if not decision:
            return None
        return {
            "decided_at": decision.decided_at.isoformat()
            if decision.decided_at
            else None,
            "intensity": decision.intensity,
            "cct": decision.cct,
            "reason": decision.reason,
            "source": decision.source,
            "manual_override_applied": bool(decision.manual_override_applied),
        }

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

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: launch recurring jobs once FastAPI triggers the lifespan hook.
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

        try:
            yield
        finally:
            # Shutdown: ensure the scheduler stops cleanly with the application.
            try:
                scheduler.shutdown(wait=False)
            except Exception:  # noqa: BLE001
                pass

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    # Expose shared services immediately so tests and dependent modules can access them.
    app.state.scheduler = scheduler
    app.state.control_service = control_service
    app.state.ai_controller = ai_controller
    app.state.rate_limiter = rate_limiter
    app.state.logging_configured = True
    app.state.settings = settings
    app.state.fernet = fernet

    def require_admin_token(authorization: str | None = Header(None)) -> None:
        if not settings.admin_token:
            raise HTTPException(status_code=503, detail="Admin token not configured")
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid token")
        token = authorization.split(" ", 1)[1]
        if token != settings.admin_token:
            raise HTTPException(status_code=401, detail="Unauthorized")

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
            return JSONResponse(
                status_code=400, content={"detail": "No features available"}
            )
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
            db.query(FeatureRow).order_by(FeatureRow.created_at.desc()).first()
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
            db.query(FeatureRow).order_by(FeatureRow.created_at.desc()).first()
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
    def healthz():
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
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

    @app.get("/diagnostics/dali")
    def dali_diagnostics(db: Session = Depends(get_db)) -> dict[str, Any]:
        mode = (
            "mock"
            if isinstance(control_service.dali, MockDALIController)
            else "hardware"
        )
        diagnostics = control_service.dali.diagnostics()

        sensor_probe_supported = False
        sensor_probe: dict[str, Any] | None = None
        read_sensor = getattr(control_service.dali, "read_sensor", None)
        if callable(read_sensor):
            try:
                probe = read_sensor()
                if isinstance(probe, dict):
                    sensor_probe = probe
                elif probe is not None:
                    sensor_probe = {"raw": probe}
                sensor_probe_supported = True
            except NotImplementedError:
                sensor_probe_supported = False
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to probe DALI sensor", extra={"error": str(exc)}
                )
        latest_sensor = (
            db.query(RawSensorEvent)
            .order_by(RawSensorEvent.timestamp.desc())
            .first()
        )
        latest_decision = (
            db.query(Decision).order_by(Decision.decided_at.desc()).first()
        )
        sensor_event_count = db.query(RawSensorEvent).count()
        decision_count = db.query(Decision).count()

        return {
            "mode": mode,
            "diagnostics": diagnostics,
            "supports_sensor_probe": sensor_probe_supported,
            "sensor_probe": sensor_probe,
            "latest_sensor_event": serialize_sensor_event(latest_sensor),
            "sensor_event_count": sensor_event_count,
            "latest_decision": serialize_decision(latest_decision),
            "decision_count": decision_count,
        }

    @app.post("/admin/aggregate-now", dependencies=[Depends(require_admin_token)])
    def aggregate_now(db: Session = Depends(get_db)):
        aggregate_features(db, settings.feature_window_minutes)
        return {"ok": True}

    @app.post("/profile", status_code=status.HTTP_201_CREATED)
    def upsert_profile(
        payload: ProfileSubmission, db: Session = Depends(get_db)
    ) -> dict[str, str]:
        data = payload.model_dump()
        encrypted = fernet.encrypt(json.dumps(data).encode("utf-8")).decode("utf-8")
        profile = (
            db.query(ParticipantProfile)
            .filter(ParticipantProfile.user_id == payload.user_id)
            .one_or_none()
        )
        now = datetime.utcnow()
        if profile:
            profile.encrypted_payload = encrypted
            profile.updated_at = now
            created = False
        else:
            profile = ParticipantProfile(
                user_id=payload.user_id,
                encrypted_payload=encrypted,
                created_at=now,
                updated_at=now,
            )
            db.add(profile)
            created = True
        db.commit()
        return {"status": "created" if created else "updated"}

    @app.get("/profile/{user_id}")
    def get_profile(
        user_id: str,
        db: Session = Depends(get_db),
    ) -> dict[str, object]:
        profile = (
            db.query(ParticipantProfile)
            .filter(ParticipantProfile.user_id == user_id)
            .one_or_none()
        )
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        try:
            decrypted = fernet.decrypt(profile.encrypted_payload.encode("utf-8"))
        except InvalidToken as exc:
            logger.error("Failed to decrypt profile", extra={"error": str(exc)})
            raise HTTPException(status_code=500, detail="Profile is corrupted") from exc
        data = json.loads(decrypted)
        data.setdefault("user_id", user_id)
        data["consent"] = bool(data.get("consent", True))
        return data

    @app.delete(
        "/admin/profile/{user_id}",
        dependencies=[Depends(require_admin_token)],
        status_code=status.HTTP_200_OK,
    )
    def delete_profile(
        user_id: str,
        db: Session = Depends(get_db),
    ) -> dict[str, bool]:
        profile = (
            db.query(ParticipantProfile)
            .filter(ParticipantProfile.user_id == user_id)
            .one_or_none()
        )
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        db.delete(profile)
        db.commit()
        return {"ok": True}

    frontend_dir = Path(__file__).resolve().parent / "frontend"
    if frontend_dir.exists():
        app.mount("/ui", StaticFiles(directory=frontend_dir, html=True), name="ui")

    return app


app = create_app()


__all__ = ["create_app", "app"]
