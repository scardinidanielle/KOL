# Security & Privacy

Smart Lighting AI is designed to handle occupant telemetry and personal preferences responsibly. This guide summarises controls, data handling, and retention expectations.

## Data classification

| Data type | Source | Storage | Notes |
|-----------|--------|---------|-------|
| Sensor events | Occupancy + lux sensors | `raw_sensor_events` table | No personal identifiers. |
| Weather events | External weather feed | `weather_events` table | Optional enrichment. |
| Feature rows | Aggregated sensor + profile features | `features` table | Input to AI; includes derived age buckets, chronotype, and occupancy rates. |
| Decisions & telemetry | Control outcomes | `decisions`, `telemetry` tables | Contains setpoints, reasons, and energy estimates. |
| Participant profiles | Operator-supplied preferences | `participant_profiles` table | Payload encrypted with Fernet. |
| Manual overrides | Manual scheduling | `manual_overrides` table | Stores override reason and expiry. |

## Encryption

- **At rest**: `ParticipantProfile.encrypted_payload` is encrypted using Fernet with the server-side `FERNET_KEY`. The key must be a 32-byte base64 string and should be stored in a secure secret manager.
- **In transit**: Deploy behind TLS (for example, reverse proxy or application gateway). The service itself does not terminate TLS.
- **AI payloads**: Feature windows forwarded to OpenAI are JSON-encoded and constrained by `PAYLOAD_CAP_BYTES` (default `2048`). Oversized payloads are rejected locally, preventing accidental leakage of large datasets.

## Authentication & authorisation

- `/admin/aggregate-now` and `/admin/profile/{user_id}` require a bearer token that must match `ADMIN_TOKEN`. Missing or incorrect tokens result in HTTP 401.
- Non-admin routes (ingest, predict, control, profiles) are open but subject to rate limiting (60 requests/minute per client IP).
- Rotate the admin token regularly and keep it separate from general operator credentials.

## OpenAI integration

- The OpenAI client activates automatically when `OPENAI_API_KEY` is present. Remove or leave this variable empty to keep the system in fallback-only mode.
- `OPENAI_MODEL` lets you specify an approved model; defaults to `gpt-4o-mini` if unset. Consider using dedicated tenants or network policies to control outbound traffic.
- Responses are clamped and validated (`clamp_intensity`, `clamp_cct`) to avoid aberrant outputs.

## Logging

- Logs are JSON-formatted to stdout via `logging_config.configure_logging`. Sensitive payloads are not logged by default, but admin operations may include metadata in the `extra` field.
- Forward logs to a secure aggregation system (e.g., Windows Event Forwarding, ELK, Azure Monitor). Ensure tokens and secrets are redacted before central storage.

## Data retention

A nightly retention job purges aged data according to `retention.py`:

| Table | Environment setting | Default |
|-------|---------------------|---------|
| Raw sensor events | `retention_raw_days` | 30 days |
| Feature rows | `retention_feature_days` | 90 days |
| Decisions & telemetry | `retention_decision_days` | 180 days |
| Manual overrides (grace) | `retention_override_grace_seconds` | 60 seconds past expiry |

Adjust these values via environment settings to align with corporate retention schedules.

## Data subject rights & consent

- The profile schema includes a `consent` flag (defaults to `true`). Respect removal requests by deleting the profile using the admin-protected endpoint.
- Because encrypted profiles are opaque without the Fernet key, destroying the key is a secure way to render stored data unreadable when retiring an environment.

## Secrets management checklist

1. Generate a unique `FERNET_KEY` per environment.
2. Store `ADMIN_TOKEN`, `FERNET_KEY`, and optionally `OPENAI_API_KEY` in a secret vault or platform-specific secure store.
3. Limit filesystem permissions on `.env` files when used.
4. Never commit secrets to source control; use placeholder values in documentation and scripts.

## Incident response tips

- Review structured logs for `detail` fields when HTTP 401/429/500 responses spike.
- Use `/healthz` to confirm scheduler and DALI status before escalating to facilities teams.
- If a token leak is suspected, rotate `ADMIN_TOKEN` immediately and restart the service to pick up the change.
