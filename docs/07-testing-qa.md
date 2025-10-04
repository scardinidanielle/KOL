# Testing & QA

Quality assurance combines automated pytest suites, manual acceptance checks in the `/ui` console, and lightweight performance sanity tests.

## Automated tests

### Pytest

```powershell
cd C:\workspace\smart_lighting_ai_dali
.\.venv\Scripts\Activate.ps1
$Env:USE_MOCK_DALI = "true"
pytest
```

- Tests cover ingest, prediction/control flows, admin security, AI controller edge cases, logging setup, and mock/real DALI switching logic.
- Keep `USE_MOCK_DALI=true` to avoid hardware dependencies.

### Linting & static checks

- The project targets Black-style formatting. Run `python -m black .` if additional formatting checks are required.
- Add `ruff` or `mypy` per team standards (not bundled by default).

## Manual acceptance

Perform these steps on staging before production releases:

1. **Profile lifecycle** – Create a profile via `/ui`, fetch it, then delete it using an admin token. Confirm encrypted payloads exist in `participant_profiles` and the decrypted response matches inputs.
2. **Ingest + predict + control** – Submit sensor and weather samples, run `/predict`, and ensure `/control` executes with expected intensity/CCT.
3. **Manual override** – Send a `/control` request with `"manual_override": true` and `"override_minutes": 15`, then issue another `/control` to confirm override persists until expiry.
4. **Health monitoring** – Verify `/healthz` reports `scheduler: running` and accurate DALI diagnostics (mock or hardware).
5. **Rate limiting** – Fire more than 60 requests within a minute and expect HTTP 429, ensuring throttling functions as designed.

Document outcomes in your release checklist.

## Performance sanity

- **Prediction latency**: Measure `/predict` response times under expected load (target <1s when OpenAI is active; faster in fallback mode).
- **Control throughput**: Confirm the anti-flicker guard (`min_update_interval_seconds`, default 5s) suits the environment. Use the mock controller to simulate rapid commands.
- **Scheduler drift**: Monitor feature aggregation timestamps; they should occur at the configured interval (`feature_window_minutes`).

## Test data management

- The SQLite database can be reset between test runs by deleting `smart_lighting.db`.
- When using external databases, wrap tests in transactions or use disposable schemas.
- `scripts/simulate_sensor.py` and `scripts/ingest_weather.py` provide repeatable data feeds for soak testing.

## Release gating checklist

- ✅ Automated pytest suite passes.
- ✅ Manual acceptance steps completed.
- ✅ Performance sanity checks within thresholds.
- ✅ Secrets rotated if required and documented in the change record.
