# Implementation Plan - Full Design Build

Last Updated: 2025-09-20 (Phase 3 telemetry & dispatcher audit)

## Implementation Status

- Core gameplay loops (theories, expeditions, recruitment, defection negotiations, mentorship) remain stable and exercised through Discord commands backed by persistence.
- LLM-enhanced multi-layer press now powers expeditions, defection negotiations, symposium calls, and admin interventions while maintaining template fallbacks.
- Telemetry dashboards, layered press cadence for mentorship/admin beats, and automated archive hosting remain the active polish items for Phase 3 completion.

## Infrastructure Utilization

1. **Offers Table** – ✅ Actively used for poach/counter offer chains with follow-up scheduling.【F:great_work/state.py†L208-L362】【F:great_work/service.py†L520-L760】
2. **Follow-ups System** – ✅ Drives negotiation deadlines, grudge timers, and sideways opportunities.【F:great_work/state.py†L344-L420】【F:great_work/service.py†L1996-L2059】
3. **Defection Logic** – ✅ Exposed via `/poach`, `/counter`, `/view_offers` and resolves probabilistically with scars and relationship updates.【F:great_work/discord_bot.py†L294-L458】【F:great_work/service.py†L572-L760】
4. **Career Progression** – ✅ Mentorship queue and lab assignment commands progress scholars during digests.【F:great_work/service.py†L1024-L1105】【F:great_work/service.py†L1934-L1995】
5. **Press Templates** – ⚠️ `MultiPressGenerator` now powers expedition, defection, symposium, and admin narratives with scheduled follow-ups; mentorship and maintenance events still publish single-layer copy.【F:great_work/service.py†L300-L2060】【F:great_work/multi_press.py†L1-L520】
6. **Event Sourcing** – ✅ Append-only event log covers all major actions and exports via `/export_log`.【F:great_work/state.py†L18-L170】【F:great_work/discord_bot.py†L577-L637】
7. **Influence System** – ✅ Five-dimensional influence with reputation caps governs costs and rewards.【F:great_work/service.py†L677-L835】
8. **Telemetry Pipeline** – ⚠️ Collector ingests metrics from every slash command with player/channel context plus LLM latency and pause events; dashboards and layered-press counters are still outstanding.【F:great_work/telemetry.py†L12-L520】【F:great_work/telemetry_decorator.py†L12-L80】【F:great_work/discord_bot.py†L786-L940】

## Implementation Phases

### Phase 1 – Core Gameplay ✅ (Delivered Sprint 1)
- `/conference` command with wager resolution
- Mentorship commands and career progression
- Deterministic expedition queue/resolver with sideways hooks
- Basic admin overrides

### Phase 2 – Community Features ✅ (Delivered Sprint 2)
- Multi-stage defection arcs with offer escrow
- Symposium scheduler with voting tables
- Admin moderation surface (`/gw_admin`)
- Static web archive exporter (manual publish)

### Phase 3 – Polish & Narrative ⚠️ In Progress
- LLM persona voice integration ⚠️ core expedition/defection/symposium/admin flows enhanced; extend coverage to theory/table-talk surfaces.
- Multi-layer press rollout ⚠️ layered coverage spans expeditions/defections/symposium/admin flows; add mentorship/admin maintenance cadences and digest highlights.
- Telemetry coverage & dashboards ⚠️ all slash commands emit telemetry with channel metrics, LLM latency, and pause events; build dashboards, layered-press counts, and alerting next.
- Archive publishing automation ⚠️ scheduler exports the archive each digest and posts a ZIP snapshot to the admin channel; automate external hosting and snapshot rotation.
- Documentation pass for deployment/config ⚠️ pending.

## 1. Mentorship System and Scholar Careers – **Complete**
- Player-driven mentorship queue with `/mentor`, lab assignment with `/assign_lab`.
- Mentorships persist in `mentorships` table and activate during digests.
- Tests cover queue/resolve logic and press output.

## 2. Conference Mechanics – **Complete**
- `/conference` launches debates, `resolve_conferences()` adjudicates outcomes with reputation deltas.
- Conferences stored in `conferences` table and resolved during digests.
- Press and events emitted on launch and resolution.

## 3. Generic Order Batching Infrastructure – **In Progress**
- Shared `orders` table now tracks mentorship activations and conference resolutions; digest processing consumes due orders via the dispatcher helpers while preserving legacy tables for history.【F:great_work/state.py†L360-L520】【F:great_work/service.py†L1402-L1880】
- **Remaining work:** migrate follow-ups and other delayed actions to the dispatcher, surface queue-depth telemetry, and write migration/backfill tooling for existing deployments.【F:great_work/state.py†L360-L520】

### 3.1 Shared Orders Design – ⚙️ Ongoing refinement

- **Schema outline:**
  - Table `orders` with columns `id` (PK), `order_type` (text), `actor_id` (text, nullable), `subject_id` (text, nullable), `payload` (JSON), `scheduled_at` (ISO timestamp, nullable), `status` (enum: `pending`, `active`, `completed`, `cancelled`), `created_at`, `updated_at`, and optional `source_table`/`source_id` for legacy linkage.
  - Composite indexes on `(status, scheduled_at)` for efficient polling and on `(order_type, status)` for type-specific queries.
- **Dispatcher contract:**
  - New `GameState` helpers: `enqueue_order(...)`, `next_orders(order_type, now)`, `mark_order_completed(order_id, result)`, `cancel_order(order_id, reason)`.
  - Service layer consumers (mentorship activation, conference resolution, future systems) request work via the dispatcher rather than bespoke table scans.
- **Migration approach:**
  - Maintain existing `mentorships` and `conferences` tables for historical data; insert a bridging order row (`order_type='mentorship_activation'`/`'conference_resolution'`) whenever new records are created.
  - Backfill pending rows at migration time by scanning existing tables and seeding `orders` entries referencing the legacy primary keys via `source_table`/`source_id`.
- **Processing loop adjustments:**
  - Replace `get_pending_mentorships()`/`get_pending_conferences()` with dispatcher polls inside `GameService` (`_resolve_mentorships`, `resolve_conferences`). The payload carries the minimal data needed to process (scholar IDs, supporters, etc.).
  - Telemetry should track order lifecycle events (enqueue, start, completion) to surface queue depth in `/telemetry_report`.
- **Future use:**
  - Follow-ups currently live in `followups`; once the dispatcher is stable, migrate them into `orders` (new `order_type='followup:defection_grudge'` etc.) to unify all delayed actions.

## 4. Sideways Discovery Mechanics – **Complete**
- Sideways discoveries map to `SidewaysEffect` payloads (faction shifts, queued conferences, opportunities).
- `_apply_sideways_effects()` handles mechanical impact and press releases.
- Tests cover effect mapping and integration.

## 5. Symposium Implementation – **Complete / Enhancement backlog**
- Weekly symposium scheduler launches topics, players vote via `/symposium_vote`, results resolve through `resolve_symposium()`.
- **Enhancement:** replace static topic list with player-proposed topics and richer digest summaries.【F:great_work/scheduler.py†L52-L86】

## 6. Admin Tools and Moderation – **Complete**
- `/gw_admin` group exposes reputation/influence adjustments, forced defection, and expedition cancellation with audit press.
- Permission gating enforced via Discord admin privileges.

## 7. Multi-stage Defection Arcs – **Complete**
- `/poach`, `/counter`, `/view_offers` drive negotiations with escrowed influence, follow-up scheduling, and probabilistic resolution.
- Relationship scars and contract updates applied on resolution.

## 8. Public Web Archive – **Partial**
- Static site generator produces searchable HTML, scholar profiles, timelines, and permalinks via `/export_web_archive` and `/archive_link`; Gazette scheduler now triggers automatic exports to `web_archive/` and publishes timestamped ZIP snapshots to the admin channel after each digest.【F:great_work/scheduler.py†L20-L124】【F:great_work/discord_bot.py†L20-L230】【F:great_work/web_archive.py†L416-L520】
- Operators have a runbook covering snapshot retention, manual export, and recovery steps (`docs/internal/ARCHIVE_OPERATIONS.md`).
- **Remaining work:** fold the runbook into external-facing docs (README/deployment guide) and automate snapshot pruning/long-term archiving.

## 9. LLM Narrative Integration – **Partial**
- `LLMClient` now orchestrates expedition launches/resolutions, defection negotiations, symposium updates, and admin notices with persona prompts, retries, pause detection, and metadata captured in press records.【F:great_work/service.py†L300-L1850】【F:great_work/llm_client.py†L1-L400】【F:tests/test_game_service.py†L80-L196】
- **Remaining work:** wire LLM enhancement into theory/table-talk surfaces, expand moderator blocklists, and expose generation statistics through telemetry dashboards.

## 10. Multi-layer Press Integration – **In Progress**
- Expedition, defection, and symposium flows now invoke `MultiPressGenerator`, queuing delayed gossip, faction statements, and analysis pieces that publish over time via the scheduled press queue.【F:great_work/service.py†L300-L1850】【F:great_work/multi_press.py†L1-L520】【F:great_work/state.py†L1-L220】
- **Remaining work:** extend layered coverage to mentorship/admin maintenance events, expose cadence configuration in settings, and tighten alignment between scheduled drops and Gazette digest summaries.

## 11. Telemetry and Operational Reporting – **Partial**
- Telemetry collector persists metrics in `telemetry.db`; `/telemetry_report` now includes LLM latency/failure stats, pause/resume events, and channel-level usage summaries for every command.【F:great_work/telemetry.py†L72-L520】【F:great_work/telemetry_decorator.py†L12-L67】【F:great_work/discord_bot.py†L720-L814】
- **Remaining work:** surface layered press counts and engagement dashboards, add digest-runtime gauges, and expose success metrics in the operator documentation.

## Phase 3 Detailed Plan – Narrative & Operations

The remaining Phase 3 work is broad. We will execute it in deliberate slices so gameplay stays stable and reviews remain manageable.

1. **LLM Foundations** – ⚠️ Partial
   - Configurable retries/back-off, mock mode, and synchronous helpers are live in `great_work/llm_client.py`; blocklists need further curation.
   - Health instrumentation feeds pause detection and admin notifications; expose key settings in operator docs.
   - **Remaining:** document configuration knobs and operational guidance for enabling the local LLM stack.

2. **LLM-Backed Expeditions, Defections & Symposium/Admin** – ✅ Complete
   - Expedition launches/resolutions, defection negotiations, symposium flows, and admin overrides invoke the LLM with persona metadata and template fallbacks.
   - Generated text is archived with provenance metadata and pause/resume logic halts actions on sustained failures.
   - Regression tests validate persona metadata and pause behaviour in mock mode.

3. **Extend Coverage to Symposium & Admin Flows** – ⚠️ Partial
   - Symposium announcements, votes, and resolutions now ship through `_enhance_press_release`; admin tools emit LLM-enhanced artefacts.
   - Mentorship activations and digest summaries still rely on static templates.
   - **Next:** audit remaining commands (table talk, mentorship completions) for persona integration and public visibility.

4. **Pause/Resume Infrastructure** – ✅ Complete
   - `GameService` tracks LLM health with exponential pause windows, admin notification queues, and `/gw_admin resume_game` unpauses once healthy.
   - Scheduler skips digests when paused and forwards status messages to the admin channel.
   - Manual resume and notification flows verified via tests and Discord command wiring.

5. **Telemetry Expansion** – ⚠️ Partial
   - Decorator now shares the bot's `GameService`, emitting command usage with player context, channel metrics, and LLM latency/failure telemetry.
   - `/telemetry_report` surfaces LLM activity, pause events, and top-channel usage; next add layered-press counts and trend dashboards for operators.

6. **Archive Automation & Docs** – ⚠️ Partial
   - Digest scheduler now exports the web archive automatically after each tick and posts a timestamped ZIP to the admin channel; the operator runbook captures retention, recovery, and manual export steps.
   - **Remaining:** automate delivery to a public host, add snapshot pruning scripts, and fold the runbook guidance into primary deployment docs.

7. **Validation & Stabilisation** – ⚠️ Partial
   - Expanded tests cover LLM enhancement flows, pause triggers, and symposium outcomes.
   - **Next:** broaden smoke tests for admin pause/resume and add telemetry assertions before release.

## Current Test Coverage

- Repository defines **186** test functions across the `tests/` suite; targeted Phase 3 scenarios pass locally (`pytest tests/test_llm_client.py tests/test_service_edge_cases.py tests/test_symposium.py tests/test_game_service.py -q`).
- Tests cover expeditions, mentorship, conferences, offers, sideways effects, telemetry, multi-press, and state edge cases.
- **Action:** wire the remaining command integration tests into CI and expand coverage for admin pause/resume plus archive snapshot rotation once automation lands.

## Testing Strategy

- Maintain unit coverage for new service methods and data-layer helpers.
- Add integration tests when wiring multi-layer press or LLM calls to prevent regressions.
- Extend snapshot checks for archive output when automated publishing is introduced.

## Success Metrics – **Partially Implemented**

- Feature completion tracking: ✅ core gameplay metrics captured via events.
- Command usage telemetry: ⚠️ partial – instrumentation spans all commands with player/channel context, but layered-press counts and engagement dashboards are still pending.
- Press accessibility: ⚠️ partial – static archive exists locally but lacks automated distribution.
- Performance metrics: ✅ scheduler timing and command durations recorded where decorator is applied.
- Player engagement metrics (symposium participation, archive hits): ⛔ not instrumented.

## Risks & Mitigations

- **Narrative cadence gap:** Layered press fires immediately; add scheduling controls and finish persona coverage for mentorship/table-talk before scaling content.
- **Telemetry blind spots:** Extend instrumentation prior to live pilots to avoid operating without usage data.
- **Operational toil:** External archive hosting and config docs are still manual—automate delivery and capture deployment prerequisites for operators.

## Upcoming Focus

1. Build telemetry dashboards that surface layered press counts, digest runtimes, and engagement trends from the expanded metrics.
2. Automate archive hosting and snapshot pruning while integrating the runbook guidance into public deployment docs.
3. Migrate remaining follow-up queues onto the shared orders dispatcher and add queue-depth telemetry/alerts.
4. Add cadence controls to `MultiPressGenerator` (mentorship/admin layering, digest highlights) without regressing current press output.
5. Publish deployment/configuration notes for the Discord bot, channel routing, and local LLM persona stack.
