# Getting Started

This guide walks through workstation setup, configuration, and how to run Smart Lighting AI for DALI with either production hardware or the built-in mock controller.

## Prerequisites

- Python 3.11+
- Git
- (Production) Tridonic DALI USB interface and drivers installed on the host

## 1. Clone and create a virtual environment

```powershell
# From PowerShell
cd C:\workspace
git clone https://example.com/smart_lighting_ai_dali.git
cd smart_lighting_ai_dali
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> On Unix-like shells, activate with `source .venv/bin/activate`.

## 2. Configure environment

Create a `.env` file or export variables in your shell. The service uses Pydantic settings so values can come from `.env`, environment variables, or process managers.

| Setting | Purpose | Example |
|---------|---------|---------|
| `FERNET_KEY` | Required 32-byte base64 key used to encrypt participant profiles. | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ADMIN_TOKEN` | Bearer token required for `/admin/*` routes and destructive profile operations. | `admin-token-placeholder` |
| `USE_MOCK_DALI` | Set to `true` to run without DALI hardware using `MockDALIController`. | `true` |
| `OPENAI_API_KEY` | Enables OpenAI-backed setpoints when present. Leaving it empty keeps AI offline. | `sk-...` |
| `OPENAI_MODEL` | Optional override for the chat-completions model. Defaults to `gpt-4o-mini`. | `gpt-4o-mini` |
| `PAYLOAD_CAP_BYTES` | Maximum request payload size forwarded to OpenAI. Must be ≥512. | `2048` |

> There is no separate `ENABLE_OPENAI` flag in code—providing `OPENAI_API_KEY` is the on/off switch.

### Sample PowerShell bootstrap

```powershell
# Generate and persist secrets for the current session
$Env:FERNET_KEY = (python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
$Env:ADMIN_TOKEN = "replace-with-admin-token"
$Env:USE_MOCK_DALI = "true"
$Env:OPENAI_MODEL = "gpt-4o-mini"
$Env:PAYLOAD_CAP_BYTES = "2048"
```

For production deployments, store secrets in your process manager (for example, Windows Service Manager, systemd, or container orchestrators) rather than in `.env` committed to source control.

## 3. Initialize the database

The application defaults to SQLite (`sqlite:///./smart_lighting.db`). Tables auto-create on first run, but you can warm them up:

```powershell
uvicorn smart_lighting_ai_dali.main:app --port 8000 --log-level info
# Once the service starts successfully, stop it with Ctrl+C.
```

To use PostgreSQL or another backend, set `DB_URL`/`db_url` in the environment.

## 4. Run the service

### Development (auto-reload, mock DALI)

```powershell
$Env:USE_MOCK_DALI = "true"
uvicorn smart_lighting_ai_dali.main:app --reload --port 8000
```

### Production (real DALI hardware)

1. Install the Tridonic DALI USB drivers (see [Hardware Integration](04-hardware-integration.md)).
2. Clear the mock flag: `Remove-Item Env:USE_MOCK_DALI` or set it to `false`.
3. Start uvicorn as a service or via a process manager:

```powershell
uvicorn smart_lighting_ai_dali.main:app --host 0.0.0.0 --port 8000
```

## 5. Verify

- Browse to `http://localhost:8000/ui` for the local console.
- Call the health check:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/healthz"
```

A healthy response contains overall status plus database, DALI, and scheduler states.

## 6. Switching between mock and real DALI

- **Mock mode** (`USE_MOCK_DALI=true`): Uses `MockDALIController` with deterministic light state and simulated sensors. Ideal for CI, testing, and development.
- **Real mode** (`USE_MOCK_DALI=false` or unset): Uses `TridonicUSBInterface` to emit DT8 commands to connected luminaires. Requires a functioning USB interface and driver stack.

Restart the service after toggling the flag to ensure the correct controller is loaded.
