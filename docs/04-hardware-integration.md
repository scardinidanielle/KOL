# Hardware Integration

This guide covers how to connect Smart Lighting AI to real DALI luminaires using a Tridonic USB interface, plus how to fall back to the built-in mock controller for labs.

## Bench setup overview

1. **DALI bus** – Wire a compliant DALI power supply and loop through the fixtures under test.
2. **Tridonic DALI USB interface** – Connect the interface to the DALI bus and to the host PC via USB.
3. **Host computer** – Runs the FastAPI service and uvicorn, exposing the `/control` endpoint that issues DT8 commands.

When `USE_MOCK_DALI=true`, steps 1–2 are optional; the service uses `MockDALIController` to simulate DT8 behaviour without hardware.

## Windows driver installation

1. Download the latest Tridonic DALI USB drivers from the vendor site.
2. Install the package with administrative privileges.
3. Verify device recognition in *Device Manager → Ports (COM & LPT)* (it typically enumerates as a virtual COM port).
4. Note the COM port if additional tooling is used; Smart Lighting AI accesses the interface directly through the provided USB driver, so no extra configuration is required in the application.

## Configure the application for hardware mode

1. Ensure `USE_MOCK_DALI` is unset or set to `false`.
2. Provide the mandatory `FERNET_KEY` and `ADMIN_TOKEN` values as described in [Getting Started](01-getting-started.md).
3. Start the service:

```powershell
# PowerShell
Remove-Item Env:USE_MOCK_DALI -ErrorAction SilentlyContinue
uvicorn smart_lighting_ai_dali.main:app --host 0.0.0.0 --port 8000
```

On startup, `create_app` instantiates `TridonicUSBInterface`, which converts control requests into DT8 payloads and sends them to the last fixture (`address=0xFF`).

## First-light test

After wiring and powering the DALI loop:

1. Seed basic telemetry (optional but helpful for AI predictions):

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/ingest/sensor" -Body '{"ambient_lux":300,"presence":true}' -ContentType 'application/json'
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/ingest/weather" -Body '{"weather_summary":"clear"}' -ContentType 'application/json'
```

2. Trigger a manual control command:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/control" -Body '{"intensity":60,"cct":4000,"reason":"first light","source":"commissioning"}' -ContentType 'application/json'
```

3. Confirm the fixture responds. Check `/healthz` for diagnostic status:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/healthz"
```

A successful test returns `"dali": "ok"` with last intensity/CCT values.

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---------|--------------|------------|
| `/healthz` reports `"dali": "idle"` after control attempts | No commands sent yet or interface not receiving power. | Issue a manual `/control` request; verify DALI power supply and wiring. |
| `/healthz` shows `"dali": "unknown"` | Interface raised an exception. | Review uvicorn logs for errors; confirm driver installation and that only one process accesses the interface. |
| Fixture flickers or ignores rapid commands | Anti-flicker guard blocked updates (`min_update_interval_seconds`). | Increase interval between commands or adjust the setting in configuration management. |
| AI predictions return 400 errors about payload size | Feature payload exceeds `PAYLOAD_CAP_BYTES`. | Reduce `feature_history_rows`, shorten retention, or raise the cap (≥512 bytes) while staying within model limits. |
| Using mock controller but lights still change | Service restarted without resetting `USE_MOCK_DALI`. | Set `$Env:USE_MOCK_DALI = "true"` before launch and restart the service. |

## Mock controller diagnostics

- The mock interface logs each command to stdout with JSON fields `intensity`, `cct`, and `applied`.
- `/healthz` exposes `status: "ok"`, plus the most recent intensity and CCT values.
- Use `scripts/simulate_sensor.py` to stream deterministic sensor readings while in mock mode.

## Safety reminders

- De-energize circuits before rewiring the DALI loop.
- Follow manufacturer current limits on the DALI power supply.
- Keep firmware and driver packages up to date to maintain compatibility and security.
