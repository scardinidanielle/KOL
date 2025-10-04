# UI Guide

The `/ui` route serves a lightweight local console for operators. It is a static application bundled with Tailwind CSS and vanilla JavaScript, so it runs entirely in the browser while invoking the FastAPI endpoints described in the API reference.

## Launching the console

1. Start the FastAPI service (`uvicorn smart_lighting_ai_dali.main:app`).
2. Navigate to `http://localhost:8000/ui`.
3. Optionally enter the admin bearer token at the top-right input so admin-only buttons can send authenticated requests.

## Layout overview

| Section | Purpose | Related API calls |
|---------|---------|-------------------|
| **Header** | Displays the console title and accepts the admin token once per session. | Attached to all admin requests. |
| **Consent & Profile** | Create, fetch, or delete encrypted participant profiles. Inputs include consent, age, impairment, chronotype, schedules, and preferences. | `POST /profile`, `GET /profile/{user_id}`, `DELETE /admin/profile/{user_id}` |
| **Control** | Manually send an intensity and CCT to the lighting system. | `POST /control` |
| **Automation** | Trigger AI predictions or force feature aggregation. | `POST /predict`, `POST /admin/aggregate-now` |
| **Quick Scenes** | Apply pre-defined scenes (Focus, Collaborate, Relax, Night) that send tailored control payloads. | `POST /control` |
| **Ingest** | Submit sensor and weather samples to build feature history. | `POST /ingest/sensor`, `POST /ingest/weather` |
| **Monitoring** | Refresh telemetry history and service health. | `GET /telemetry`, `GET /healthz` |
| **Telemetry History** | Shows up to 10 recent telemetry entries. | `GET /telemetry` |
| **Response Pane** | Latest JSON response rendered with timestamp for quick troubleshooting. | All routes |

## Using the console effectively

### Profiles

- Fill out the form and click **Save Profile** to encrypt and store preferences. The payload is encrypted using the server-side Fernet key before being persisted.
- Click **Load Profile** to fetch and display decrypted content (consent defaults to `true` when missing).
- **Delete Profile** requires a valid admin token. Upon success, the profile is removed from the database.

### Control and scenes

- Manual control requests send `{ "source": "console" }` by default; quick scenes use `{ "source": "scene" }` with a descriptive reason.
- The mock DALI controller applies anti-flicker limits, so repeated rapid commands may show `manual_override_applied: false` but reuse the previous state when updates occur within the configured minimum interval.

### Automation

- **Predict** posts an empty body and lets the server choose the default history window (`feature_history_rows`). If no feature data exists, a 400 response (`{"detail": "No features available"}`) appears in the response pane.
- **Aggregate Now** is an admin action that immediately computes a feature window and stores it for upcoming predictions.

### Ingest

- Sensor ingest accepts ambient lux (`0–1000`) and a presence flag. Weather ingest captures summary text plus optional temperature.
- Use the ingest forms to seed data before requesting predictions when running in a fresh database.

### Monitoring

- **Load Telemetry** fetches paginated decisions. The UI displays either the raw array or the `items` property returned by the API.
- **Refresh Health** fetches `/healthz`, which lists database status, DALI diagnostics, and scheduler state.

### Response pane tips

- Errors render as `{ status, data }`. For rate-limited responses, look for HTTP 429 and adjust your request cadence (defaults allow 60 requests per minute per client).
- Copy responses directly into support tickets or logs to aid remote troubleshooting.

## Keyboard shortcuts & reset

The UI is intentionally simple and does not implement custom keyboard shortcuts. Reloading the page clears the response pane and cached telemetry.

## When to prefer the API directly

Use direct API calls or automation scripts when:

- Integrating with building management systems
- Running batch ingest or telemetry exports
- Performing authenticated admin actions from CI pipelines where embedding the admin token in a browser is not acceptable

The UI remains a safe, operator-focused companion for labs, demos, and local investigations.
