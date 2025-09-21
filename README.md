# The Great Work

[![Version](https://img.shields.io/badge/version-1.0.0--rc1-blue)](https://github.com/tachyon-beep/jubilant-fortnight)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
![Tests](https://img.shields.io/badge/tests-283%20passing-brightgreen)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/23ff623516b548409a9b28c0e6490fed)](https://app.codacy.com/gh/tachyon-beep/jubilant-fortnight/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![Codacy Badge](https://app.codacy.com/project/badge/Coverage/23ff623516b548409a9b28c0e6490fed)](https://app.codacy.com/gh/tachyon-beep/jubilant-fortnight/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_coverage)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

The Great Work is an asynchronous, fully public research drama played entirely through Discord. Players guide scholars, publish bold theories, and orchestrate expeditions where spectacular failure still creates story.

## Table of Contents

1. [Features at a Glance](#features-at-a-glance)
2. [Architecture Snapshot](#architecture-snapshot)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Running & Deployment](#running--deployment)
6. [Testing & Tooling](#testing--tooling)
7. [Operational Playbook](#operational-playbook)
8. [Contributing](#contributing)
9. [Roadmap & Release Planning](#roadmap--release-planning)
10. [License](#license)

## Features at a Glance

- **Living Scholars** – 20–30 named scholars persist across campaigns with memories, scars, loyalty snapshots, and defection arcs.
- **Public Confidence Wagers** – every theory carries a reputation stake (+2/−1 up to +15/−25), and the Gazette immortalises the outcome.
- **Expedition Pipeline** – think tanks, field digs, and great projects with sideways failure tables that turn disasters into content.
- **Five-Faction Influence Economy** – Academic, Government, Industry, Religious, and Foreign pools power recruitment, seasonal commitments, faction projects, and archive endowments.
- **Layered Press System** – gossip, scheduled briefs, faction memos, and admin updates generated automatically with tone packs and Guardian moderation.
- **Operational Toolkit** – telemetry collector, `/telemetry_report`, KPI calibration CLI, seasonal simulation harness, deployment smoke checks, archive mirroring, Guardian safety plan.
- **Semantic Search (optional)** – Qdrant vector DB with sentence-transformers embeddings for knowledge, press, and future retrieval tooling.

## Architecture Snapshot

| Layer | Responsibilities | Key Modules |
| --- | --- | --- |
| Presentation | Discord slash commands, ChannelRouter routing, admin workflows. | `great_work/discord_bot.py`, `ChannelRouter`, `gw_admin` |
| Service | Game orchestration, scheduler, seasonal economy, telemetry hooks, Guardian integration. | `service.py`, `scheduler.py`, `multi_press.py`, `telemetry.py` |
| Domain | Scholars, expeditions, offers, press templates, YAML assets. | `models.py`, `state.py`, `expeditions.py`, `press.py`, `data/` |
| Data/Ops | SQLite persistence, telemetry DB, archive export, operational CLIs. | `GameState`, `telemetry.db`, `web_archive/`, `great_work/tools/` |

Further reading: [High-Level Design](docs/design/HLD.md) · [System Architecture](docs/design/SYSTEM_ARCHITECTURE.md).

## Quick Start

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-repo/the-great-work.git
   cd the-great-work
   ```

2. **Create a virtual environment**

   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -e .[dev]

   # Alternatively, use the Makefile helpers
   make venv && make install && make env
   ```

3. **Configure environment variables**

   ```bash
   cp .env.example .env
   # Edit .env with your Discord token, channel IDs, etc.
   ```

4. **Seed the database**

   ```bash
   make seed
   # or: python -m great_work.tools.seed_db var/state/great_work.db
   ```

5. **Run smoke checks & tests (recommended)**

   ```bash
   python -m great_work.tools.deployment_smoke
   make test
   ```

6. **Start the bot**

   ```bash
   make run
   # or: python -m great_work.discord_bot
   ```

## Configuration

### Required

| Variable | Description |
| --- | --- |
| `DISCORD_TOKEN` | Bot token from the Discord Developer Portal. |
| `DISCORD_APP_ID` | Application ID for command registration. |
| `GREAT_WORK_CHANNEL_ORDERS` | Fallback channel for operational output. |

### Recommended channel mapping

Set whichever IDs match your server; informational commands broadcast to the first configured channel in this priority order.

| Variable | Purpose |
| --- | --- |
| `GREAT_WORK_CHANNEL_TABLE_TALK` | Player-facing status embeds and gossip. |
| `GREAT_WORK_CHANNEL_GAZETTE` | Gazette digest posts. |
| `GREAT_WORK_CHANNEL_UPCOMING` | Optional teaser channel for scheduled drops. |
| `GREAT_WORK_CHANNEL_ADMIN` | Admin notifications (moderation hits, calibration snapshots). |

### Guardian moderation

| Variable | Description |
| --- | --- |
| `GREAT_WORK_GUARDIAN_MODE` | `sidecar` (HTTP RPC) or `local` (load weights directly). |
| `GREAT_WORK_GUARDIAN_URL` | Sidecar scoring endpoint (e.g., `http://localhost:8085/score`). |
| `GREAT_WORK_GUARDIAN_LOCAL_PATH` | Path to local model weights when `local` mode is used. |
| `GREAT_WORK_GUARDIAN_CATEGORIES` | Enabled categories (e.g., `HAP,sexual,violence,self-harm,illicit`). |
| `GREAT_WORK_MODERATION_STRICT` | `true` pauses gameplay when Guardian is offline; set to `false` for prefiler-only mode. |

### Telemetry & alerts

`python -m great_work.tools.recommend_kpi_thresholds --apply` persists guardrails into `var/telemetry/telemetry.db` (the default telemetry store). Environment overrides remain useful for experiments.

```
GREAT_WORK_ALERT_WEBHOOK_URLS=https://ops.example/webhook,https://oncall.example/webhook
GREAT_WORK_ALERT_COOLDOWN_SECONDS=300
GREAT_WORK_ALERT_MIN_ACTIVE_PLAYERS=3
GREAT_WORK_ALERT_MIN_MANIFESTO_RATE=0.5
GREAT_WORK_ALERT_MIN_ARCHIVE_LOOKUPS=1
GREAT_WORK_ALERT_MAX_SEASONAL_DEBT=25
GREAT_WORK_ALERT_MIN_NICKNAME_RATE=0.3
GREAT_WORK_ALERT_MIN_PRESS_SHARES=1
```

### Archive & calibration

```
GREAT_WORK_ARCHIVE_PUBLISH_DIR=web_archive_public
GREAT_WORK_ARCHIVE_PAGES_ENABLED=true
GREAT_WORK_ARCHIVE_PAGES_DIR=/opt/the-great-work-pages
GREAT_WORK_ARCHIVE_PAGES_SUBDIR=archive
GREAT_WORK_ARCHIVE_MAX_STORAGE_MB=512

GREAT_WORK_CALIBRATION_SNAPSHOTS=true
GREAT_WORK_CALIBRATION_SNAPSHOT_DIR=calibration_snapshots
GREAT_WORK_CALIBRATION_SNAPSHOT_KEEP=12
GREAT_WORK_CALIBRATION_SNAPSHOT_DETAILS=true
```

### LLM (optional)

```
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=
LLM_MODEL_NAME=gpt-4o-mini
LLM_TEMPERATURE=0.8
LLM_MAX_TOKENS=500
LLM_TIMEOUT=30
LLM_RETRY_ATTEMPTS=3
LLM_RETRY_SCHEDULE=1,3,10,30
LLM_BATCH_SIZE=10
LLM_SAFETY_ENABLED=true
LLM_USE_FALLBACK=true
```

See `.env.example` for the full template.

### Embeddings & Qdrant (optional)

Enable semantic search and future retrieval features with Qdrant + embeddings.

```
# Qdrant connection
QDRANT_URL=http://localhost:6333
COLLECTION_NAME=great-work-knowledge

# Embedding model (SentenceTransformer name)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Auto-index new press releases into Qdrant (GameService)
GREAT_WORK_QDRANT_INDEXING=true
```

Basic operations (see docs/QDRANT_SETUP.md):

```
# Start Qdrant locally
docker-compose up -d qdrant

# Create/verify collection sized to the model
python -m great_work.tools.qdrant_manager --setup

# Index built-in knowledge samples
python -m great_work.tools.qdrant_manager --index

# Check stats
python -m great_work.tools.qdrant_manager --stats
```

## Running & Deployment

- **Local development:** `make run` after filling `.env`. Guardian is optional; set `GREAT_WORK_MODERATION_STRICT=false` when developing without it.
- **Docker Compose:** `docker compose up -d` starts the bot, telemetry dashboard, and archive server. View logs with `docker compose logs -f bot`.
- **Guardian sidecar:** see [DEPLOYMENT.md](DEPLOYMENT.md#guardian-sidecar-operations) for setup and validation steps.
- **Archive & GitHub Pages:** digest snapshots land in `web_archive_public/`; configure `GREAT_WORK_ARCHIVE_PAGES_*` to mirror into a Pages repository.
- **Qdrant embeddings:** optional setup documented in [docs/QDRANT_SETUP.md](docs/QDRANT_SETUP.md).

## Testing & Tooling

| Command | Purpose |
| --- | --- |
| `python -m great_work.tools.deployment_smoke` | Validates environment, channel routing, Guardian configuration, and alert fan-out. |
| `pytest -q` or `make test` | Full unit/integration suite (283+ tests). |
| `python -m great_work.tools.simulate_seasonal_economy --config scenario.json` | Dry-run seasonal commitment & mentorship tuning scenarios. |
| `python -m great_work.tools.recommend_kpi_thresholds --apply` | Persist KPI guardrail recommendations to telemetry DB. |
| `python -m great_work.tools.export_product_metrics` | Export KPI snapshots, history, and cohorts to JSON/CSV. |
| `python -m great_work.tools.validate_narrative --all` | Lint narrative YAML/tone packs. |
| `python -m great_work.tools.preview_narrative ...` | Render sample press output for review. |

## Operational Playbook

- [Deployment Guide](DEPLOYMENT.md)
- [Telemetry Runbook](docs/TELEMETRY_RUNBOOK.md)
- [Guardian Safety Plan](docs/archive/SAFETY_PLAN.md)
- [Implementation Plan](docs/archive/implementation_plan.md) · [Gap Analysis](docs/archive/gap_analysis.md)
- [Archive Log](docs/archive/ARCHIVE_LOG.md)

## Contributing

1. Fork and clone the repository.
2. Create a virtual environment and install dev dependencies (`pip install -e .[dev]`).
3. Run `python -m great_work.tools.deployment_smoke` to confirm setup.
4. Add tests for your changes; `pytest -q` should pass.
5. Run `ruff check .` / `ruff format .` if available.
6. Open a PR referencing relevant issues, noting smoke/test results and any operational impacts.

## Roadmap & Release Planning

- Post-launch concepts live in [ROADMAP.md](ROADMAP.md).
- The 1.0.0-rc1 packaging steps are tracked in [RELEASE_1_0_RC_CHECKLIST.md](RELEASE_1_0_RC_CHECKLIST.md).
- Historical changes are recorded in [CHANGELOG.md](CHANGELOG.md).

## License

Released under the [MIT License](LICENSE).
