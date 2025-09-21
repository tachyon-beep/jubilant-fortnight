# Sprint 2 — Comprehensive Change List for Pull Request

## TL;DR

- Consolidates the multi-layer press system, orders dispatcher, telemetry dashboard, and long-tail
  economy (investments, archive endowments, seasonal commitments, faction projects).
- Adds Guardian moderation guardrails, archive export + snapshots, and admin tools for
  orders dispatcher visibility and intervention.
- Docs for post-1.0 ideas were moved under `docs/post_1_0/`; the 1.0 PR focuses on core
  gameplay, transparency, and observability.

Scope is sized for playtests and operational trial; guardrails and runbooks included.

## Major Features & Enhancements

### 0. Moderation & Safety Guardrails

- Integrated Guardian moderation for player inputs and generated press copy
- Added safety runbook notes and configuration toggles

### 1. Multi-Layer Press System & Narrative Enhancements

- Implemented multi-layer press releases for expedition, defection, symposium, and admin flows
- Added recruitment layer for new scholars joining the research community
- Introduced "table talk" flavor commentary with persona-aware responses
- Created press tone system with customizable personality packs
- Extended press templates to all major game events
- Added contract upkeep influence sink with automated debt tracking and reprisals
- Expanded layered press for recruitment and table-talk, including faction briefings and commons roundups
- Added recruitment followup scheduling with delayed outcomes
- Implemented sideways effects system with 220+ faction-specific narrative impacts
- Created comprehensive vignette catalogue with 150+ narrative snippets
- Completed narrative arcs with defection epilogues and sidecast phases
- Added mentorship press templates with progression/completion narratives

### 2. Telemetry & Monitoring System

- Built comprehensive telemetry system with channel metrics and event tracking
- Added LLM latency monitoring and performance metrics
- Implemented pause/resume infrastructure for handling LLM failures
- Created telemetry dashboard (Docker-based) for real-time monitoring
- Added telemetry decorators to all Discord commands
- Exposed orders dispatcher telemetry with order snapshots and backlog metrics
- Added symposium scoring telemetry with reprisal tracking
- Integrated seasonal commitments and faction project metrics

### 3. Shared Orders Dispatcher

- Implemented unified delayed action processing system
- Centralized management of scheduled game events
- Improved reliability of asynchronous game mechanics
- Added `/gw_admin list_orders` and `cancel_order` for operator intervention
- Exposed orders dispatcher metrics in telemetry dashboard
- Automated migration from legacy followups table

### 4. LLM Integration Enhancements

- Enhanced LLM client with persona metadata support
- Added fallback templates for graceful degradation
- Implemented mock mode for testing without API calls
- Added comprehensive error handling and retry logic

### 5. Web Archive System

- Automatic web archive export with ZIP snapshots
- Archive hosting for press releases and game history
- Admin channel integration for archive management

### 6. Game Mechanics Enhancements

- Added recruitment odds preview command showing detailed probability calculations
- Implemented contract upkeep system with influence debt tracking
- Added automated reprisal mechanics for contract defaults
- Enhanced expedition resolution with sideways effects
- Improved scholar personality expression through vignettes
- Introduced faction investments and archive endowments as long-tail influence sinks with press/telemetry coverage
- Expanded symposium backlog/status commands to explain scoring components and reprisal cadence for weekly topics

### 7. Long-Tail Economy Features

- **Seasonal Commitments**: 28-day player-faction contracts with relationship-based cost modifiers
- **Faction Projects**: Collaborative infrastructure builds with progress tracking and completion rewards
- **Faction Investments** (`/invest`): Direct influence spending for faction infrastructure and goodwill
- **Archive Endowments** (`/endow_archive`): Reputation-earning donations to the public archive
- **Relationship Integration**: All economy features now factor in mentorship/sidecast history for cost/reward calculations
- **Admin Controls**: `/gw_admin` commands for creating/updating commitments and projects

## Compatibility & Migrations

- Legacy `followups` table is automatically migrated to the orders dispatcher `orders` queue on
  first run. No manual action required. great_work/state.py:510
- Some documentation and conceptual work that is post-1.0 has been moved to
  `docs/post_1_0/` to reduce churn in the release PR.

## Documentation Updates

- Added comprehensive [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) (1500+ lines)
- Created [GAME_ENHANCEMENTS.md](GAME_ENHANCEMENTS.md) with feature proposals (including Qdrant integration)
- Updated [README.md](../README.md) for 1.0.0 with install/deploy guides
- Added [CHANGELOG.md](../CHANGELOG.md) documenting all features
- Created [RELEASE_1.0_CHECKLIST.md](../RELEASE_1.0_CHECKLIST.md) for release preparation
- Reorganized documentation structure (moved internal docs to docs/internal/)
- Authored [TELEMETRY_RUNBOOK.md](TELEMETRY_RUNBOOK.md) with health checks, thresholds, incident response
- **Comprehensive Writing Guide Update**: see [WRITING_GUIDE.md](WRITING_GUIDE.md)
- Created issue tracking system with template and resolved first issue
- Added deployment documentation with systemd examples in [deployment.md](deployment.md)
- Created `docs/post_1_0/` and moved post‑1.0 concepts there (e.g.,
  [USER_TELEMETRY.md](post_1_0/USER_TELEMETRY.md),
  [TELEMETRY_COHORT_COMPARISONS.md](post_1_0/TELEMETRY_COHORT_COMPARISONS.md))

## Testing Improvements

- Expanded test coverage for telemetry, LLM, orders dispatcher, and multi-press features
- Added tests for scheduler, table talk, and digest highlights
- Updated tests to support channel_id parameters
- Verified layered press scheduling and release mechanisms
- Added recruitment odds, contract upkeep, and sideways vignette tests
- New suites: `test_commitments_projects.py`, `test_influence_sinks.py`
- Relationship modifier testing for recruitment and commitments
- Expanded symposium tests with scoring and reprisal validation

Tests also run in CI for enforcement.

## Infrastructure & DevOps

- Docker Compose configuration for telemetry dashboard
- Systemd service example for production deployment
- Enhanced .gitignore with comprehensive patterns
- Cleaned up project structure for production release

## Code Quality & Maintenance

- Fixed all 68 markdown linting issues
- Resolved all Codacy warnings
- Bumped version to 1.0.0-rc1
- Cleaned up development artifacts and caches
- Reorganized AI agent documentation to .claude/ directory

## Files Changed Summary

- 125 files changed, 25,909 insertions, 4,231 deletions (current)
- Major refactoring of agent documentation
- Complete overhaul of multi-press and service modules
- Significant expansion of telemetry and monitoring capabilities
- Massive expansion of GameService with economy features
- New database tables for commitments, projects, investments, endowments

## Key Metrics

- Implementation progress: 71.4% of requirements fully implemented (55 of 77)
- 255 tests passed, 1 skipped in 21.98s (local)
- Linting passes locally; CI enforces Ruff and pytest
- New Discord commands: `/invest`, `/endow_archive`, `/seasonal_commitments`, `/faction_projects`, `/recruit_odds`
- Enhanced Admin Tools: `/gw_admin list_orders`, `/gw_admin cancel_order`, `/gw_admin resume_game`

## Commit Highlights (oldest → newest)

1. `39abb28` Update documentation and add contributor guide
2. `cec69a6` Major Phase 3 improvements: telemetry, orders dispatcher, multi-layer press
3. `423b277` Apply project updates
4. `6b2db32` Layer recruitment and table talk press
5. `c7e8eea` Expose symposium scoring telemetry and reprisal handling
6. `f54839d` Add recruitment odds preview and contract upkeep sinks
7. `529ab35` Enrich layered press for recruitment and table talk
8. `1512f44` Layer recruitment followups
9. `9083430` Expose orders dispatcher telemetry
10. `292dbd2` Complete narrative arcs
11. `6f605a9` Expand vignette catalogue
12. `44ad824` Tie seasonal commitments and faction projects to relationship history
13. `76afd1a` Introduce long-tail influence sinks and surface economy controls
14. `93f645e` Add telemetry guardrails and ops runbook
15. `5662eaa` Automate archive publishing and document safety guardrails
16. `eca5bd8` Integrate Guardian moderation guardrails
17. `40c65ff` Tie moderation and safety into flows
18. `a69c2dd` Tie sideways vignette tags to mechanical effects
19. `b95d563` Instrument seasonal commitment telemetry alerts
20. `d353815` Calibrate telemetry KPIs and seasonal alerts

## Ops & Configuration

- LLM client
  - `LLM_MODE=mock` to run offline; `LLM_RETRY_ATTEMPTS`; `LLM_USE_FALLBACK`
  - Optional `LLM_RETRY_SCHEDULE="1,3,10,30,60"`
- Scheduler and archive
  - `GREAT_WORK_ARCHIVE_PUBLISH_DIR` (e.g., `web_archive_public`)
  - `GREAT_WORK_ARCHIVE_PAGES_ENABLED`, `GREAT_WORK_ARCHIVE_PAGES_DIR`, `GREAT_WORK_ARCHIVE_PAGES_SUBDIR`,
    `GREAT_WORK_ARCHIVE_PAGES_NOJEKYLL`
  - Snapshot controls: `GREAT_WORK_ARCHIVE_MAX_SNAPSHOTS`, `GREAT_WORK_ARCHIVE_MAX_STORAGE_MB`
- Alerts and guardrails
  - Digest: `GREAT_WORK_ALERT_MAX_DIGEST_MS`, `GREAT_WORK_ALERT_MAX_QUEUE`, `GREAT_WORK_ALERT_MIN_RELEASES`
  - Dispatcher: `GREAT_WORK_ALERT_MAX_ORDER_PENDING`, `GREAT_WORK_ALERT_MAX_ORDER_AGE_HOURS`
  - Seasonal/Symposium debt: `GREAT_WORK_ALERT_MAX_SEASONAL_DEBT`, `GREAT_WORK_ALERT_MAX_SYMPOSIUM_DEBT`

## Risk & Rollback

- Risks: slow digests, orders dispatcher backlog, archive publish failures, debt reprisal loops
- Mitigations: telemetry dashboard, admin `/gw_admin list_orders` and cancel tools, alerts
- Rollback: disable publishing, set `LLM_MODE=mock`, pause/resume game, revert container; schema
  additions are backward compatible and safe to leave in place

## Reviewer Validation Guide

- Run `/recruit_odds`, `/invest`, `/endow_archive`, `/seasonal_commitments`, `/faction_projects`
- Use `/export_web_archive` and confirm ZIP snapshot publishes during digest
- Check `/gw_admin list_orders` and cancel a test follow-up; verify telemetry reflects changes
- Open telemetry dashboard (Compose service) and verify digest, queue, and debt guardrails

<!-- Screenshots moved to README.md for visibility -->
