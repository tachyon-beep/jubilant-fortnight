# High-Level Design (HLD)

This document captures the core gameplay, systems, and design principles of **The Great Work** as it stands for the 1.0.0 release candidate. It is the player-facing complement to `docs/SYSTEM_ARCHITECTURE.md`.

## 1. Game Premise

- **Genre:** asynchronous, collaborative research drama played entirely through Discord.
- **Players:** 4–8 research leads competing for reputation while sharing scholars and discoveries.
- **Cadence:** idle-friendly; two Gazette digests per day advance time, weekly symposium invites public debate.
- **Tone:** theatrical academia in a fantastical/historical setting. Every move is public and permanent.
- **Key Pillars:**
  - **Public Performance:** no private moves—press coverage is automatic.
  - **Living Scholars:** procedural and hand-authored scholars build myths via memories, feelings, scars.
  - **Spectacular Failure:** sideways discoveries make bold risks worthwhile even when they backfire.

## 2. Core Loops

### 2.1 Publish Bold Theories
- Players submit theories with confidence stakes (`/submit_theory`).
- Confidence ladder (+2/−1 up to +15/−25) drives risk calibration.
- Gazette publishes Academic Bulletins and rival reactions.

### 2.2 Expeditions & Sideways Discoveries
- Queue expeditions (`/launch_expedition`) with scholars, prep depth, funding factions.
- Resolution uses d100 + preparation + expertise − friction.
- Outcomes: failure, partial success, solid success, landmark unlock.
- Sideways discovery tables ensure spectacular failures still generate content.

### 2.3 Influence & Economy
- Five faction influence pools (Academic, Government, Industry, Religious, Foreign).
- Actions debit/credit influence; soft caps scale with reputation.
- Long-tail sinks: seasonal commitments (`/seasonal_commitments`), faction projects (`/faction_projects`), investments (`/invest`), archive endowments (`/endow_archive`).

### 2.4 Scholars & Relationships
- Scholars progress via mentorship (`/mentor`, `/assign_lab`), lab placements, sidecasts.
- Memory model: Facts (timestamped), Feelings (decay unless scarred), Scars (permanent).
- Defection negotiations: multi-step offers, loyalty snapshots, faction-aligned press coverage.
- Sidecasts generated from YAML arcs; mentorship history surfaces in `/status` embeds.

### 2.5 Symposium & Reputation
- Weekly symposium selects topics from backlog based on scoring heuristics (age, freshness, repetition penalties).
- Players pledge influence, debate outcomes, accrue debt or reputation boosts.
- Seasonal reprisal system escalates unpaid commitments.

## 3. Narrative & Press

- **Multi-layer Press System**: fast gossip, scheduled briefs, faction memos, admin updates.
- **Tone Packs**: modular headlines/blurbs per setting; validated via `python -m great_work.tools.validate_narrative --all`.
- **Guardian Moderation**: two-pass safety on player input and generated press, with hashed overrides and telemetry tracking.
- **Archive**: every digest exports to static HTML; snapshots mirrored to GitHub Pages if enabled.

## 4. Telemetry & Operations

- Telemetry collector tracks command usage, queue depth, LLM latency, seasonal/symposium debt, Guardian events.
- `/telemetry_report` surfaces health checks; `python -m great_work.tools.export_product_metrics` archives KPI/cohort snapshots.
- Deployment smoke CLI (`python -m great_work.tools.deployment_smoke`) verifies env vars, channel routing, Guardian configuration, and alert fan-out prior to launch.
- Seasonal tuning harness (`python -m great_work.tools.simulate_seasonal_economy`) supports ops dry runs.

## 5. Safety & Moderation

- Guardian sidecar (or local model) evaluates text categories (HAP, sexual, violence, self-harm, illicit).
- Prefilter + Guardian scoring; strict mode pauses gameplay on sidecar outage.
- `/gw_admin moderation_recent`, `/gw_admin moderation_overrides`, overrides expire by default.
- Safety runbook in `docs/SAFETY_PLAN.md` defines incident response and drill cadence.

## 6. Player Commands Overview

- **Action Commands:** `/submit_theory`, `/launch_expedition`, `/mentor`, `/assign_lab`, `/poach`, `/counter`, `/recruit`, `/invest`, `/endow_archive`.
- **Information Commands:** `/status`, `/wager`, `/seasonal_commitments`, `/faction_projects`, `/symposium_status`, `/symposium_backlog`, `/gazette`, `/recruit_odds`, `/telemetry_report` (admin).
- **Admin Commands:** `/gw_admin list_orders`, `/gw_admin cancel_order`, `/gw_admin calibration_snapshot`, `/gw_admin moderation_recent`, seasonal commitment management, economy tuning.

## 7. Dependencies & Optional Modules

- Required: Python 3.12, discord.py, SQLite.
- Optional: OpenAI-compatible LLM, Guardian weights (`download_guardian_model`), Qdrant (vector search), FastAPI telemetry dashboard.

## 8. Future Roadmap

See `docs/ROADMAP.md` for post-1.0 initiatives (dynasties, conspiracies, cohort comparison tooling, player portal).

---

This HLD intentionally focuses on gameplay-facing structure. For deeper technical details refer to:
- `docs/SYSTEM_ARCHITECTURE.md` – layered architecture, data flow, integrations.
- `docs/deployment.md` – environment configuration, Guardian operations, smoke testing.
- `docs/TELEMETRY_RUNBOOK.md` & `docs/SAFETY_PLAN.md` – operational procedures.
