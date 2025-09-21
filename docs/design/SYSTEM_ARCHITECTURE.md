# System Architecture Overview

This document supplements the high-level design (HLD) with implementation-centric details. It captures how the codebase is structured today, which services interact, and where operational knobs live.

## Layered View

| Layer | Responsibilities | Primary Modules |
| --- | --- | --- |
| Presentation | Discord slash commands, embeds, admin workflows. | `great_work/discord_bot.py`, `ChannelRouter`, `gw_admin` commands |
| Service | Game orchestration, seasonal economy, multi-press generation, telemetry hooks. | `great_work/service.py`, `multi_press.py`, `scheduler.py`, `telemetry.py` |
| Domain | Core models and logic for scholars, expeditions, offers, press artefacts. | `great_work/models.py`, `state.py`, `expeditions.py`, `scholars.py`, `press.py` |
| Data & Ops | Persistence, telemetry storage, archive export, deployment utilities. | `GameState` (SQLite), `var/telemetry/telemetry.db`, `web_archive/`, tools under `great_work/tools/` |

### Presentation Layer

- **Discord Bot (`build_bot`)** – registers slash commands, wires telemetry decorator, polls Guardian sidecar.
- **ChannelRouter** – resolves where informational commands broadcast (table-talk → gazette → upcoming → orders).
- **gw_admin Commands** – operational surface for calibration snapshots, moderation overrides, seasonal adjustments, dispatcher auditing.

### Service Layer

- **GameService** – single entry point for gameplay actions (theories, expeditions, mentorships, seasonal commitments, investments). Maintains admin notification queue and interacts with telemetry/Guardian hooks.
- **MultiPressGenerator** – assembles layered press artefacts (fast gossip, scheduled follow-ups, admin briefs).
- **Scheduler (`GazetteScheduler`)** – APScheduler-backed job runner for twice-daily digests, symposium cadence, archive mirroring, calibration snapshots.
- **Simulation/Tooling** – `python -m great_work.tools.simulate_seasonal_economy`, `recommend_kpi_thresholds`, `export_product_metrics`, `deployment_smoke` support live ops rehearsals.

### Domain Layer

- **Models** – Typed dataclasses for `Scholar`, `Player`, `PressRelease`, `TheoryRecord`, etc.; emphasise deterministic seeds for reproducibility.
- **State Management (`GameState`)** – SQLite persistence with JSON columns, dedicated helpers for offers, follow-ups, seasonal commitments, investments, archive export.
- **Expedition Resolver** – d100-based resolution with preparation/expertise/friction modifiers and sideways failure catalogs.
- **Press Templates & Tone Packs** – YAML-backed reusable prose for recruitment, mentorship, sidecasts, defection epilogues, sideways vignettes.

### Data & Ops

- **SQLite (`var/state/great_work.db`)** – authoritative state (players, scholars, events, commitments, orders). Event sourcing via append-only log.
- **Telemetry (`var/telemetry/telemetry.db`, `TelemetryCollector`)** – metrics for commands, queue depth, seasonal/mentorship debt, Guardian events. Decorated slash commands emit telemetry automatically.
- **Web Archive (`web_archive/`, publish dir via `GREAT_WORK_ARCHIVE_PUBLISH_DIR`, default `public/`)** – static HTML exports triggered each digest, mirrored to GitHub Pages when enabled.
- **Guardian Sidecar** – optional moderation service; configuration controlled via `GREAT_WORK_GUARDIAN_*` env vars. Safety runbook is maintained internally.
- **Tooling** – CLI entry points under `great_work/tools/`: seeding, calibration snapshot export, smoke tests, seasonal simulations, moderation probes, narrative validation/preview.

## Data Flow

```
Player Slash Command
  -> discord_bot (command handler)
    -> GameService (validates, executes)
      -> GameState (SQLite transaction + event log)
      -> TelemetryCollector (metrics)
      -> MultiPressGenerator (press artefacts)
        -> ChannelRouter / scheduler enqueue

Scheduled Jobs (GazetteScheduler)
  -> GameService._publish_digest
    -> GameState (resolve orders, apply seasonal commitments)
    -> TelemetryCollector (digest metrics)
    -> Archive sync + calibration snapshot

Guardian Moderation
  -> discord_bot pre/post hooks
    -> Guardian sidecar (HTTP scoring)
    -> Telemetry (`moderation_recent`, overrides)
```

## Key Integrations

- **Discord API** – Slash commands, file uploads, embeds; no privileged intents required beyond message content for command responses.
- **Guardian Sidecar** – HTTP endpoints for moderation scoring (`GREAT_WORK_GUARDIAN_URL`). Strict mode pauses game on downtime.
- **APScheduler** – Cron-like scheduling inside the bot process (digests, symposium, archive maintenance).
- **FastAPI Telemetry Dashboard (`ops/telemetry-dashboard/`)** – optional container exposing `/`, `/api/kpi_history`, `/api/calibration_snapshot`, dispatcher filters, engagement cohorts.
- **Optional Qdrant Vector DB** – Skeleton hooks remain (`qdrant_setup.md`) but vector search is not critical for 1.0.

## Operational Touchpoints

- **Smoke Testing** – `python -m great_work.tools.deployment_smoke` verifies tokens, channel routing, Guardian config, alert fan-out.
- **Seasonal Tuning** – `simulate_seasonal_economy` runs dry scenarios; calibration snapshots via `/gw_admin calibration_snapshot` feed dashboards.
- **Moderation Oversight** – `/gw_admin moderation_recent`, `/gw_admin moderation_overrides`, `python -m great_work.tools.calibrate_moderation`.
- **Telemetry Guardrails** – thresholds configurable via env vars, stored in `telemetry.db` KPI targets, reported in `/telemetry_report` and alert router.

## Future Considerations

- **Externalising Scheduler** – For multi-process deployments consider moving digests to a dedicated worker with message queue.
- **Database Scaling** – SQLite suffices for pilot scale; document migration path to Postgres if concurrent writes become a concern.
- **LLM Abstraction** – Current client is OpenAI-compatible; future roadmap could add provider registry and caching.
- **Telemetry API** – Baseline endpoints exist; cohort comparison and player portal expansions tracked in `docs/ROADMAP.md`.

For gameplay-centric details, see `docs/HLD.md`. For operational runbooks, consult `../../DEPLOYMENT.md` and `docs/TELEMETRY_RUNBOOK.md`.
