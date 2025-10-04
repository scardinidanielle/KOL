# Executive Overview

Smart Lighting AI for DALI is a control platform that blends real-time building telemetry, participant preferences, and generative AI recommendations to keep luminaires comfortable, accessible, and energy efficient. The application exposes a REST API and a local web console so facilities teams can ingest sensor data, trigger AI predictions, and drive Digital Addressable Lighting Interface (DALI) fixtures with either production hardware or a high-fidelity mock controller.

Key value drivers:

- **Comfort & accessibility** – AI-driven setpoints respect occupancy, ambient lux, and user profiles that capture chronotype, visual impairments, and consent.
- **Operational resilience** – A deterministic fallback, in-memory rate limiting, and background feature aggregation keep decisions flowing even without external AI connectivity.
- **Governance-first design** – Personally identifiable data is encrypted with Fernet, admin actions require a bearer token, and retention jobs purge stale records on a schedule.

```mermaid
flowchart LR
  Sensors[Occupancy & Lux Sensors / Weather Feed / Profiles]
  API[FastAPI Service]
  DB[(SQLite / SQLAlchemy)]
  Scheduler[Feature & Retention Jobs]
  AI[OpenAI Controller<br/>(payload capped)]
  Control[Control Service]
  DALI[DALI Hardware<br/>(Mock or Tridonic USB)]
  UI[Local Web UI /ui]

  Sensors -->|/ingest| API
  API --> DB
  Scheduler --> DB
  DB -->|Feature windows| AI
  AI -->|Setpoint| Control
  Control -->|DT8 commands| DALI
  DALI -->|Diagnostics| API
  API --> UI
  UI -->|Admin + Ops| API

```

Smart Lighting AI can be deployed on a bench for rapid prototyping or in production alongside existing facility systems. With consistent APIs and encrypted storage, the platform is ready for incremental integration into enterprise energy management programs.
