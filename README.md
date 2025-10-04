# smart-lighting-ai-dali

AI-driven control surface for DALI-2 DT8 tunable-white luminaires using the Tridonic DALI USB interface.

## Features

- FastAPI service with OpenAPI documentation.
- Windowed feature store with strict payload capping for OpenAI function-calling requests.
- APScheduler background jobs for feature aggregation and retention/pruning.
- Rules-based fallback controller with accessibility and safety clamps.
- Mock DALI driver for development and automated tests plus DT8 command diagnostics.
- Encrypted personal profile storage using Fernet keys supplied via `.env`.
- Export utilities and notebook workflow for offline tuning.

## Hardware overview

- **Controller**: Tridonic DALI USB (connects to the service host).
- **Luminaires**: DALI-2 DT8 tunable white fixtures (intensity 0–100, CCT 1800–6500K).
- **Sensor**: Tridonic LS/PD LI G2 providing ambient lux and presence.

Wiring summary:

1. Connect the DALI USB interface to the DALI bus powering the DT8 luminaire loop.
2. Attach the LS/PD LI G2 sensor to the DALI bus (power + communication lines).
3. Ensure the host running this service can access the USB device (`/dev/ttyACM*`).

## Getting started

### Environment

1. Copy `.env.example` to `.env` and fill in secrets:
   ```bash
   cp .env.example .env
   ```
   - Generate a Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
   - For the sample dataset, use `FERNET_KEY=3hWrYIogeMKAoBFoQVoM23bzb1bqGTGSQhZWWSWxMgI=`.
2. Set environment keys (all optional except `FERNET_KEY`):
   - `USE_MOCK_DALI` – defaults to `false`, set to `true` for simulation mode.
   - `OPENAI_API_KEY` – optional; when unset, the rules-based fallback is used.
   - `WEATHER_API_KEY` – optional upstream integration key.
   - `DB_URL` – database connection string (default SQLite file).
   - `ADMIN_TOKEN` – Bearer token required for secure admin calls (example: `super-secret-admin-token`).
3. Install dependencies:
   ```bash
   pip install -e .[dev]
   ```
4. Initialize the database (SQLite by default):
   ```bash
   python -c "from smart_lighting_ai_dali.db import Base, engine; Base.metadata.create_all(bind=engine)"
   ```

### Running the API

Local execution:
```bash
python -m smart_lighting_ai_dali.scripts.run_api
```

Docker compose snippet:
```yaml
services:
  api:
    build: .
    environment:
      - DB_URL=postgresql+psycopg://user:pass@db:5432/smart_lighting
      - FERNET_KEY=${FERNET_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    ports:
      - "8000:8000"
    devices:
      - "/dev/ttyACM0:/dev/ttyACM0"
```

API docs available at `http://localhost:8000/docs`.

### Simulation mode

Enable the mock controller (`USE_MOCK_DALI=true`) to run the entire stack without physical DALI hardware. In separate terminals:

```bash
python scripts/simulate_sensor.py --interval 2 --duration 30
python scripts/ingest_weather.py --interval 60 --duration 5
uvicorn smart_lighting_ai_dali.main:app --reload
```

The mock controller mirrors DT8 anti-flicker behaviour, and telemetry grows as `/control` decisions are issued.

### Loading example data

1. Load the encrypted personal profile:
   ```bash
   python - <<'PY'
   import json
   from cryptography.fernet import Fernet
   from smart_lighting_ai_dali.db import session_scope
   from smart_lighting_ai_dali.models import PersonalProfile
   from smart_lighting_ai_dali.config import get_settings

   settings = get_settings()
   with open("smart_lighting_ai_dali/data/examples/personal.json", "r", encoding="utf-8") as handle:
       blob = json.load(handle)

   with session_scope() as session:
       session.add(PersonalProfile(profile_id=blob["profile_id"], encrypted_payload=blob["encrypted_payload"]))
   print("stored profile")
   PY
   ```
2. Trigger feature aggregation job manually if needed:
   ```bash
   python - <<'PY'
   from smart_lighting_ai_dali.db import session_scope
   from smart_lighting_ai_dali.feature_engineering import aggregate_features

   with session_scope() as session:
       aggregate_features(session, window_minutes=5)
   PY
   ```

### Making predictions and control calls

```bash
http POST :8000/predict
http POST :8000/control intensity=55 cct=4000 reason="manual tweak" manual_override:=true override_minutes:=30
```

The `/predict` endpoint only reads the most recent feature windows (1–3 rows) ensuring payloads stay under 2 KiB. `/control` applies DALI DT8 commands, stores decisions, respects anti-flicker guards, and manages manual overrides that auto-expire after 30 minutes.

### Admin endpoint

Trigger feature aggregation on demand with a Bearer token:

```bash
http POST :8000/admin/aggregate-now "Authorization:Bearer super-secret-admin-token"
```

The endpoint responds with `{ "ok": true }` when the aggregation runs successfully.

## Data policy and retention

- **Raw ingestion**: every sensor and weather event is stored in immutable tables (`raw_sensor_events`, `weather_events`).
- **Feature windows**: aggregation job compresses 5-minute windows storing summary statistics; only these compact rows feed the OpenAI API.
- **Payload caps**: `payload_cap_bytes` (default 2048 bytes) and `payload_batch_limit` (<=3 windows) prevent oversized AI requests.
- **Retention**: background pruning keeps raw data 30 days, features 90 days, decisions & telemetry 180 days (configurable via `.env`).
- **Exports**: `scripts/export_training_data.py` generates CSV/Parquet for offline tuning.

## Privacy and security

- Personal profiles are stored encrypted with Fernet keys sourced from environment variables.
- Logs use structured JSON and mask personal payloads; only derived features are logged for AI calls.
- Simple rate limiting protects the public API; prefer running behind an HTTPS reverse proxy in production.

## Notebook workflow

`notebooks/tuning_workflow.ipynb` demonstrates how to:

1. Pull raw events and feature rows from the database.
2. Build rolling statistics for model tuning.
3. Plot energy-saving metrics and daylight correlations.

## Tests & CI

Run locally:
```bash
pytest
flake8 smart_lighting_ai_dali tests
mypy smart_lighting_ai_dali
```

GitHub Actions workflow `.github/workflows/ci.yml` runs formatting, type checks, and tests on every push.

## API reference (abridged)

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/ingest/sensor` | Store LS/PD LI G2 readings |
| POST | `/ingest/weather` | Store weather updates |
| POST | `/predict` | Query OpenAI with compact feature payload |
| POST | `/control` | Issue DT8 command and record decision |
| GET | `/telemetry` | Paginated decision telemetry |
| GET | `/healthz` | Service, hardware, and scheduler diagnostics |

## Energy-saving metric

Every decision records `energy_saving_estimate = (100 - intensity)/100` to quantify reductions versus full output. Telemetry can be visualized via the notebook.

## License

Released under the MIT License. See [LICENSE](LICENSE).
