from __future__ import annotations

import json
import os
import tempfile
from importlib import reload
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

TEST_FERNET_KEY = "3hWrYIogeMKAoBFoQVoM23bzb1bqGTGSQhZWWSWxMgI="

temp_dir = Path(tempfile.mkdtemp())
os.environ.setdefault("FERNET_KEY", TEST_FERNET_KEY)
os.environ.setdefault("DB_URL", f"sqlite:///{temp_dir / 'test.db'}")
os.environ.setdefault("USE_MOCK_DALI", "true")
os.environ.setdefault("ADMIN_TOKEN", "test-token")
BASE_DIR = Path(__file__).resolve().parents[1]

from smart_lighting_ai_dali import config  # noqa: E402

config.get_settings.cache_clear()  # type: ignore[attr-defined]
settings = config.get_settings()

from smart_lighting_ai_dali import db  # noqa: E402

reload(db)

from smart_lighting_ai_dali.db import Base, engine, SessionLocal  # noqa: E402
from smart_lighting_ai_dali.main import create_app  # noqa: E402
from smart_lighting_ai_dali.models import (  # noqa: E402
    Decision,
    FeatureRow,
    ManualOverride,
    ParticipantProfile,
    PersonalProfile,
    RawSensorEvent,
    Telemetry,
    WeatherEvent,
)

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="session")
def session() -> Generator:
    SessionLocal.configure(bind=engine)  # type: ignore[attr-defined]
    session = SessionLocal()  # type: ignore[call-arg]
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def app(session):  # noqa: ANN001
    app = create_app(settings=settings, use_mock_dali=True)
    personal_path = (
        BASE_DIR / "smart_lighting_ai_dali" / "data" / "examples" / "personal.json"
    )
    with open(personal_path, "r", encoding="utf-8") as handle:
        blob = json.load(handle)
    if not session.query(PersonalProfile).count():
        session.add(
            PersonalProfile(
                profile_id=blob["profile_id"],
                encrypted_payload=blob["encrypted_payload"],
            )
        )
        session.commit()
    if not session.query(ParticipantProfile).count():
        session.add(
            ParticipantProfile(
                user_id=blob["profile_id"],
                encrypted_payload=blob["encrypted_payload"],
            )
        )
        session.commit()
    yield app
    try:
        app.state.scheduler.shutdown(wait=False)
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture
def client(app):  # noqa: ANN001
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session(session):  # noqa: ANN001
    yield session


@pytest.fixture(autouse=True)
def cleanup(db_session):  # noqa: ANN001
    yield
    models = (
        Decision,
        FeatureRow,
        RawSensorEvent,
        WeatherEvent,
        ManualOverride,
        Telemetry,
        ParticipantProfile,
    )
    for model in models:
        db_session.query(model).delete()
    db_session.commit()
