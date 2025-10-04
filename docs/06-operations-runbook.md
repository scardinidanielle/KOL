# Operations Runbook

This runbook covers day-two operations for Smart Lighting AI, including startup, health checks, log review, backups, and common troubleshooting steps.

## Service start & stop

### Start (PowerShell example)

```powershell
# Ensure environment variables are set (FERNET_KEY, ADMIN_TOKEN, etc.)
cd C:\workspace\smart_lighting_ai_dali
.\.venv\Scripts\Activate.ps1
uvicorn smart_lighting_ai_dali.main:app --host 0.0.0.0 --port 8000 --log-level info
```

### Stop

- Press `Ctrl+C` in the foreground session, or
- Send `Stop-Process -Name uvicorn` when running as a console app, or
- Use your service manager (e.g., NSSM, systemd) to stop gracefully.

The application shuts down the APScheduler background jobs on exit.

## Health checks

- **HTTP health**: `GET /healthz` returns overall status plus database, DALI interface diagnostics, and scheduler state.

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/healthz"
```

- **Database connectivity**: On success the response includes `"database": "ok"`. Failures are logged with `"Database health check failed"`.
- **Scheduler**: `"scheduler": "running"` indicates aggregation and retention jobs are active.

## Background jobs

| Job | Trigger | Purpose |
|-----|---------|---------|
| Feature aggregation | Interval (`feature_window_minutes`, default 5) | Summarises recent sensor data into feature rows. |
| Retention pruning | Nightly at 00:00 | Deletes stale sensor, feature, decision, weather, telemetry, and manual override records per retention settings. |

Use `/admin/aggregate-now` to trigger aggregation manually (requires admin token).

## Logs

- Logs emit JSON to stdout/stderr. Capture them via process manager or redirect to files:

```powershell
uvicorn smart_lighting_ai_dali.main:app --host 0.0.0.0 --port 8000 *> logs\smart-lighting.json
```

- Key log messages:
  - `"Mock DALI applied setpoint"` – indicates mock controller state transitions.
  - `"Manual override stored"` – manual override persisted.
  - `"Feature row created"` – background job succeeded.
  - `"Database health check failed"` – investigate database connectivity.

## Backups & restores

Default deployments use SQLite (`smart_lighting.db` in the project root).

### Backup procedure

1. Stop the service to avoid partial writes.
2. Copy the database file to secure storage:

```powershell
Copy-Item .\smart_lighting.db "D:\backups\smart_lighting\smart_lighting_$(Get-Date -Format yyyyMMdd_HHmmss).db"
```

3. Archive logs if needed.

### Restore procedure

1. Stop the service.
2. Replace `smart_lighting.db` with the desired backup copy.
3. Restart the service and verify `/healthz` and `/telemetry` responses.

For managed databases (PostgreSQL, etc.), follow platform-specific snapshot procedures.

## Scaling & performance

- **Concurrency**: uvicorn defaults to a single worker. Increase workers (`--workers 2`) when CPU cores and database concurrency allow.
- **Rate limiting**: The in-memory limiter uses client IP. Behind a proxy, ensure `Forwarded` headers are preserved or terminate rate limiting at the edge.
- **Payload caps**: `PAYLOAD_CAP_BYTES` protects outbound AI calls. Increase cautiously if feature payloads grow.

## Troubleshooting quick reference

| Symptom | Action |
|---------|--------|
| HTTP 401 on admin routes | Confirm `ADMIN_TOKEN` in request header; restart service after rotating token. |
| HTTP 429 responses | Requests exceed rate limit. Back off for 60 seconds or increase limits via settings. |
| `/predict` returns 400 `No features available` | Ingest sensor/weather data or trigger `/admin/aggregate-now`. |
| Control commands ignored | Check for active manual overrides via database or logs; respect anti-flicker interval. |
| Scheduler reported `stopped` | Restart the service. Scheduler auto-starts on boot; repeated stops indicate upstream exceptions (check logs). |
| Fernet decryption errors in logs | Stored profile payloads corrupted or Fernet key rotated without re-encryption. Restore from backup or purge affected profiles. |

## Maintenance calendar

- **Daily**: Review `/healthz`, logs, and telemetry anomalies.
- **Weekly**: Run `pytest` in staging, validate UI flows, rotate admin token if policy mandates.
- **Monthly**: Verify retention jobs by checking record counts, review OpenAI usage, test backup restore.
