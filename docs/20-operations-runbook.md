# Operations Runbook

## Lifecycle
- `main.py` uses FastAPI lifespan to start the scheduler, register aggregation and retention jobs, and open the DALI interface.
- Shutdown waits for running jobs, flushes telemetry, and releases USB handles before closing the DB session factory.

## Health Checks
- `GET /healthz` returns:
  - `status: ok` when API, scheduler heartbeat, and DB connectivity succeed within the timeout.
  - `status: degraded` when non-critical dependencies (OpenAI, weather) are failing.
  - `status: error` when DB or DALI drivers are unavailable; check logs immediately.

## Credential Rotation
1. Update `.env` or secret manager values (`ADMIN_TOKEN`, `OPENAI_API_KEY`, `FERNET_KEY`).
2. Restart the service so the lifespan hook reloads settings and refreshes scheduler contexts.
3. For `FERNET_KEY` changes, re-encrypt stored profiles before restart to maintain readability.

## Database Care
- Default SQLite file lives at `./smart_lighting_ai_dali.db` unless `DB_URL` overrides it.
- Retention job (`retention.py`) prunes raw events (30d), features (90d), and decisions (180d) on schedule.
- Run `/admin/aggregate-now` to refill features if ingestion outpaces pruning.

## Observability
- Structured logs emitted via `smart_lighting_ai_dali` logger hierarchy.
- Key logger names: `control_service`, `openai_client`, `feature_engineering`, `retention`, `dali.driver`.
- Typical warnings:
  - `openai_client` retry notices on 429/500 responses.
  - `db.health` warnings when the health checker catches slow queries.
  - `dali.driver` toggling to mock mode when hardware disconnects.

## Incident Playbooks
| Incident | Immediate Actions |
| --- | --- |
| No features available | Check ingestion scripts; run `/admin/aggregate-now`; verify scheduler heartbeat in logs. |
| Payload exceeds cap | Inspect payload dump in `openai_client`; reduce `PAYLOAD_BATCH_LIMIT` or adjust feature window size. |
| DB health = error | Confirm disk space; restart service; consider enabling WAL; restore from backup if corrupt. |
| DALI offline | If mock mode: restart simulator; if hardware: reseat USB, confirm `/dev/ttyACM*`, fall back to rules-only mode. |

## Backup & Restore
- Stop the service to avoid partial writes.
- Copy the SQLite file and the `./backups/` directory if present.
- To restore, replace the file with the backup copy and restart; feature aggregation will rebuild derived tables.
- For zero-downtime upgrades, run the new container pointing at the same volume after taking a snapshot.

## Upgrades
- Apply migrations if schema changed (Alembic or manual script).
- Use rolling deployment: bring up new pod with updated image, run health check, switch traffic, retire old pod.
- Ensure retention job version matches schema before resuming full traffic.

## Security Notes
- Keep `ADMIN_TOKEN` scoped and rotate quarterly; only ops endpoints require it.
- Apply principle of least privilege for host USB access and database credentials.
- Monitor audit logs for repeated admin requests or failed authentications.
