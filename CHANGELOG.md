# Changelog

All notable changes to The Great Work Discord game will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Informational commands (`/status`, `/symposium_status`, `/symposium_proposals`, `/symposium_backlog`, `/wager`, `/seasonal_commitments`, `/faction_projects`, `/gazette`, `/export_log`) now publish summaries to the configured public channels while preserving ephemeral confirmations for the caller.
- `/status` surfaces faction sentiment derived from persisted mentorship and sidecast histories so players and operators can audit relationship shifts.
- Telemetry now persists KPI targets (which automatically override alert thresholds), reports engagement cohorts (new vs returning players), and surfaces symposium participation mixes in `/telemetry_report` and the dashboard, including updated FastAPI views/templates.
- Added digest-synced calibration snapshots with `/gw_admin calibration_snapshot`, `python -m great_work.tools.export_calibration_snapshot`, and a dashboard `/api/calibration_snapshot` endpoint; snapshots summarise seasonal debt, faction investments, archive endowments, and pending orders.
- Added `python -m great_work.tools.generate_sample_telemetry` to seed deterministic telemetry data for rehearsal environments.
- Added `python -m great_work.tools.manage_orders` plus enhanced `/gw_admin list_orders` filters/file output and dashboard query controls for dispatcher audits.
- `/status`, `/symposium_backlog`, `/symposium_status`, and `/gazette` now publish rich embeds to public channels, surfacing mentorship histories, symposium scoring heuristics, and recent headlines at a glance. Mentorship/sidecast events grant small faction bonuses and broader vignettes cover espionage/sabotage beats.
- Added `python -m great_work.tools.validate_narrative --all` (and `make validate-narrative`) to statically lint tone packs, recruitment/table-talk/mentorship press, sidecast arcs, epilogues, and vignette catalogues before deployment.
- Added `python -m great_work.tools.preview_narrative` (and `make preview-narrative`) to render sample outputs for narrative surfaces, aiding content review before deploy.
- Landmark expeditions now draw copy from `great_work/data/landmark_preparations.yaml`, including dedicated follow-up briefs previewable via `python -m great_work.tools.preview_narrative landmark-prep`.
- Defection negotiations append a loyalty snapshot summarising current feelings toward the rival and patron, with the same snapshot stored on each offer record and echoed in `/view_offers`.
- Added `python -m great_work.tools.recommend_kpi_thresholds --apply` to compute KPI guardrail recommendations from recent telemetry and persist the tuned targets into `telemetry.db` (with optional JSON exports for audit trails).
- Added `python -m great_work.tools.export_product_metrics` to dump product KPIs, historical trends, and engagement cohorts into `telemetry_exports/` for offline analysis and ops reviews.
- Alert router now reads `GREAT_WORK_ALERT_WEBHOOK_URLS` alongside `GREAT_WORK_ALERT_WEBHOOK_URL`, enabling multi-channel fan-out without custom code.

## [0.9.1] - 2025-09-21 (Current – prepping 1.0.0-rc1)

### Added

#### Core Gameplay Features

- **Scholar System**: 20-30 memorable scholars with unique personalities, memories, and relationships
- **Expedition Mechanics**: Three expedition types (think tanks, field expeditions, great projects) with d100 resolution
- **Confidence Wagers**: Risk/reward system with reputation stakes (suspect +2/-1, certain +5/-7, stake_my_career +15/-25)
- **Five-Faction Influence Economy**: Academic, Government, Industry, Religious, and Foreign factions with reputation-based soft caps
- **Mentorship System**: Player-driven scholar career progression via `/mentor` and `/assign_lab` commands
- **Conference Mechanics**: Public theory debates with reputation wagering
- **Symposium Voting**: Weekly community topics with player participation

#### Advanced Features

- **Contract Negotiations**: Multi-stage poaching system with influence escrow via `/poach`, `/counter`, `/view_offers`
- **Sideways Discovery Effects**: Expeditions trigger mechanical consequences (faction shifts, theories, grudges)
- **Multi-layer Press System**: Depth-based narrative coverage for all events
- **Defection Arcs**: Complex loyalty mechanics with scars and emotional consequences

#### Discord Integration

- **20 Slash Commands**: Complete player interface for all game actions
- **Scheduled Digests**: Twice-daily automated game advancement
- **Admin Tools**: Moderation commands via `/gw_admin` command group
- **Channel Routing**: Separate channels for orders, gazette, and table talk

#### Narrative Enhancement

- **LLM Integration**: OpenAI-compatible API for dynamic persona voices
- **Content Moderation**: Multi-level safety checks with fallback templates
- **Press Archive**: All events generate permanent, citable press releases

#### Technical Infrastructure

- **Event Sourcing**: Complete audit trail of all game actions
- **Deterministic RNG**: Reproducible game mechanics for fair play
- **Web Archive**: Static HTML export with permalinks for historical records
- **Telemetry System**: Comprehensive metrics tracking with admin reporting
- **Qdrant Integration**: Vector database for semantic knowledge management

### Configuration

- Environment-based configuration via `.env` file
- Docker Compose support for containerized deployment
- Makefile automation for common development tasks
- Comprehensive test suite with 192 tests

### Documentation

- High-level design document (HLD.md)
- Requirements evaluation and gap analysis
- Implementation plan with sprint tracking
- CLAUDE.md for AI-assisted development
- Comprehensive inline code documentation

### Fixed

- All critical production bugs identified in Sprint 3
- Memory API issues in contract negotiation system
- Database schema compatibility issues
- Test suite reliability and coverage

### Security

- Content filtering for LLM-generated text
- Rate limiting on LLM API calls
- Admin permission checks on moderation commands
- Secure influence escrow system for contracts

## [0.9.0] - 2024-12-19 (Pre-release)

### Added

- Sprint 3 features: LLM integration, telemetry, multi-layer press
- Sprint 2 features: Contracts, sideways effects, web archive
- Sprint 1 features: Mentorship, conferences, symposiums, admin tools

### Known Issues

- Memory.get_feeling() method implementation
- Some edge cases in offer resolution
- Minor markdown formatting issues (resolved via Codacy patch)

## [0.1.0] - 2024-09-01 (Initial Development)

### Added

- Basic Discord bot framework
- Scholar generation system
- Expedition queueing and resolution
- Simple press release templates
- SQLite database persistence

---

## Versioning Policy

This project uses Semantic Versioning:

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

## Migration Notes

### Upgrading to 0.9.0 (on the path to 1.0.0-rc1)

- No database migrations required from 0.8.x builds
- Environment variables remain compatible
- All Discord commands maintain backward compatibility
