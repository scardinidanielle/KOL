# Glossary

| Term | Definition |
|------|------------|
| **AI controller** | Component that wraps the OpenAI client (`AIController`) and produces lighting setpoints. Falls back to deterministic logic when no API key is configured. |
| **ADMIN_TOKEN** | Environment variable containing the bearer token required for `/admin/*` endpoints and destructive profile operations. |
| **APScheduler** | Background scheduler (APScheduler) that triggers feature aggregation and retention pruning jobs. |
| **CCT (Correlated Colour Temperature)** | Describes the warmth or coolness of light in Kelvin. The system clamps values between 1,800 K and 6,500 K before issuing DT8 commands. |
| **Control Service** | Server-side component that enforces anti-flicker limits, handles manual overrides, and sends DT8 commands to the DALI interface. |
| **DALI (Digital Addressable Lighting Interface)** | Lighting control protocol used to address and dim fixtures. The project supports a mock controller and the Tridonic USB interface. |
| **DT8** | DALI device type for colour temperature control. Commands include intensity and warm/cool bytes. |
| **Feature window** | Aggregated snapshot of recent sensor, weather, and profile data used to drive predictions. |
| **FERNET_KEY** | 32-byte base64 string that encrypts participant profiles at rest. |
| **Manual override** | Temporary, operator-initiated setpoint that persists for a defined duration and supersedes AI decisions. |
| **PAYLOAD_CAP_BYTES** | Environment setting that limits the size of feature payloads forwarded to OpenAI, default 2048 bytes. |
| **Profile** | Encrypted participant preference record containing consent, age, chronotype, schedules, and preferences. |
| **Quiet hours** | Configuration settings (`quiet_hours_start`, `quiet_hours_end`) used in downstream feature engineering and control logic. |
| **Setpoint** | Pair of intensity (0–100) and CCT (1,800–6,500) values applied to fixtures. |
| **Telemetry** | Historical record of control decisions and energy savings estimates stored in the `decisions` table. |
| **USE_MOCK_DALI** | Boolean environment flag. When true, the application uses the in-memory mock controller instead of the Tridonic USB interface. |
