# Developer Guide

## Architecture Overview
| Module | Responsibility |
| --- | --- |
| `smart_lighting_ai_dali/main.py` | FastAPI app factory, lifespan scheduler wiring, route registration. |
| `smart_lighting_ai_dali/control_service.py` | Core orchestration for `/predict` and `/control`, manual override handling, guardrails. |
| `smart_lighting_ai_dali/openai_client.py` | Builds AI payloads, enforces payload cap, handles retries, parses function-call JSON. |
| `smart_lighting_ai_dali/feature_engineering.py` | Window builders, aggregation jobs, feature schemas. |
| `smart_lighting_ai_dali/models.py` | SQLAlchemy ORM models, enums, helpers. |
| `smart_lighting_ai_dali/retention.py` | Scheduled pruning routines for raw and feature tables. |
| `smart_lighting_ai_dali/dali/` | DALI DT8 driver, mock implementations, hardware adapters. |

## Local Development Setup
1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .[dev]
   ```
2. Copy `.env.example` to `.env` and set the following keys:

| Key | Purpose | Example |
| --- | --- | --- |
| `DB_URL` | SQLAlchemy URL (defaults to SQLite file). | `sqlite:///./smart_lighting.db`
| `USE_MOCK_DALI` | Toggle mock driver for local dev. | `true`
| `ENABLE_OPENAI` | Explicit toggle for AI calls. | `false`
| `OPENAI_API_KEY` | Secret for OpenAI client when enabled. | `sk-...`
| `OPENAI_MODEL` | Model name string used by client. | `gpt-4o-mini`
| `FERNET_KEY` | Encryption key for personal profiles. | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
| `PAYLOAD_CAP_BYTES` | Max outbound payload size. | `2048`
| `ADMIN_TOKEN` | Bearer token required by admin routes. | `local-admin-token`

> Missing `FERNET_KEY` prevents the app from booting because encrypted profile access fails.

## Running Locally
- Launch API with mock DALI:
  ```bash
  USE_MOCK_DALI=true uvicorn smart_lighting_ai_dali.main:app --reload
  ```
- Seed example events:
  ```bash
  python scripts/simulate_sensor.py --interval 2 --duration 60
  python scripts/ingest_weather.py --interval 60 --duration 3
  ```
- Aggregate features manually:
  ```bash
  python - <<'PY'
  from smart_lighting_ai_dali.db import session_scope
  from smart_lighting_ai_dali.feature_engineering import aggregate_features

  with session_scope() as session:
      aggregate_features(session, window_minutes=5)
  PY
  ```
- Call endpoints with `httpie` or curl/PowerShell (examples below).

## AI Payload Construction
1. `control_service.build_ai_payload()` (via `openai_client`) collects latest feature windows capped by `PAYLOAD_BATCH_LIMIT`.
2. Payload dictionary is serialized to JSON and truncated if it exceeds `PAYLOAD_CAP_BYTES`.
3. Client sends a function call request; JSON schema expects fields like `intensity`, `cct`, `reason`, `expires_at`.
4. Responses are validated; missing or malformed fields trigger the rules fallback defined in `control_service.rules_fallback()`.
5. Final outputs are clamped to safe intensity/CCT ranges before dispatch to DALI.

## Testing
- Targeted tests:
  ```bash
  pytest -k "control or predict"
  ```
- Full suite:
  ```bash
  pytest
  ```

## Extending the Models
- Add new columns or tables in `models.py`, then generate migrations if using an external DB.
- Update feature builders to surface the new data and adjust payload serialization.
- When adding a new `impairment_enum` rule:
  1. Extend the enum definition in `models.py`.
  2. Update rule handling in `control_service.apply_accessibility_rules()`.
  3. Add tests covering the new branch (`tests/test_control_service.py`).

## Endpoint Examples
### `/predict`
```bash
curl -X POST http://localhost:8000/predict \
     -H "Content-Type: application/json" \
     -d '{}'
```
```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/predict" -Body '{}' -ContentType 'application/json'
```

### `/control`
```bash
curl -X POST http://localhost:8000/control \
     -H "Content-Type: application/json" \
     -d '{"manual_override": true, "intensity": 55, "cct": 4000, "override_minutes": 30}'
```
```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/control" \
  -Body '{"manual_override": true, "intensity": 55, "cct": 4000, "override_minutes": 30}' \
  -ContentType 'application/json'
```

### `/admin/aggregate-now`
```bash
curl -X POST http://localhost:8000/admin/aggregate-now \
     -H "Authorization: Bearer ${ADMIN_TOKEN}"
```
```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/admin/aggregate-now" \
  -Headers @{ Authorization = "Bearer $env:ADMIN_TOKEN" }
```

### `/healthz`
```bash
curl http://localhost:8000/healthz
```
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/healthz"
```

## Troubleshooting
| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `.env` fails to load | Formatting or quoting issue in dotenv. | Check for stray quotes; use `KEY=value` lines only. |
| `FERNET_KEY` missing error | Key unset or malformed. | Regenerate with `Fernet.generate_key()` and export it. |
| SQLite locked | Concurrent writer while running retention job. | Wait a few seconds or run with WAL mode: `PRAGMA journal_mode=WAL;`. |
| OpenAI retries warning | Transient 429/5xx response. | Retries are automatic; confirm `ENABLE_OPENAI` and network access. |
| No features aggregated | Scheduler not running or DB empty. | Trigger `/admin/aggregate-now` and ensure ingestion scripts are active. |
