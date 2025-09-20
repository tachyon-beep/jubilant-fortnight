# Implementation Plan - Full Design Build

Last Updated: 2025-09-27 (Phase 3 telemetry & narrative refresh)

## Implementation Status

- Core gameplay loops (theories, expeditions, recruitment, defection negotiations, mentorship) remain stable and exercised through Discord commands backed by persistence.
- LLM-enhanced multi-layer press now powers expeditions, defection negotiations, symposium calls, mentorship beats, and admin interventions while maintaining template fallbacks.
- Mentorship lifecycles and admin pause/resume flows schedule layered follow-ups, deliver dual-paced fast/long drops, surface “upcoming highlights” to opt-in channels, and publish digest highlight blurbs drawn from the scheduled press queue alongside admin notifications.
- Telemetry dashboards (Discord report + bundled FastAPI dashboard) and containerised archive hosting are in place; queue depth and digest health now land in `/telemetry_report`, and remaining polish focuses on alert thresholds, operator runbooks, and external publish options.
- Recruitment odds are now exposed via `/recruit_odds`, listing faction modifiers, cooldown penalties, and influence bonuses so players can compare bids before committing.
- Contract upkeep now drains influence every digest, automatically recording contract debt and reprisals when players fall behind; `/status` surfaces per-faction upkeep and outstanding balances.

## Infrastructure Utilization

1. **Offers Table** – ✅ Actively used for poach/counter offer chains with follow-up scheduling.【F:great_work/state.py†L208-L362】【F:great_work/service.py†L520-L760】
2. **Follow-ups System** – ✅ Drives negotiation deadlines, grudge timers, and sideways opportunities.【F:great_work/state.py†L344-L420】【F:great_work/service.py†L1996-L2059】
3. **Defection Logic** – ✅ Exposed via `/poach`, `/counter`, `/view_offers` and resolves probabilistically with scars and relationship updates.【F:great_work/discord_bot.py†L294-L458】【F:great_work/service.py†L572-L760】
4. **Career Progression** – ✅ Mentorship queue and lab assignment commands progress scholars during digests.【F:great_work/service.py†L1024-L1105】【F:great_work/service.py†L1934-L1995】
5. **Press Templates** – ⚠️ `MultiPressGenerator` drives expedition, defection, symposium, mentorship, conference, and admin narratives with scheduled follow-ups and dual cadence presets, but recruitment/table-talk still ship as single beats and template variety remains limited.【F:great_work/service.py†L300-L2060】【F:great_work/multi_press.py†L1-L520】
6. **Event Sourcing** – ✅ Append-only event log covers all major actions and exports via `/export_log`.【F:great_work/state.py†L18-L170】【F:great_work/discord_bot.py†L577-L637】
7. **Influence System** – ✅ Five-dimensional influence with reputation caps governs costs and rewards.【F:great_work/service.py†L677-L835】
8. **Telemetry Pipeline** – ⚠️ Collector ingests metrics from every slash command plus layered-press cadence, digest runtimes, queue depth, and LLM latency; Discord `/telemetry_report` and the bundled FastAPI dashboard surface the aggregates, pending success-threshold tuning and escalation guidance.【F:great_work/telemetry.py†L72-L820】【F:great_work/telemetry_decorator.py†L12-L80】【F:great_work/discord_bot.py†L786-L940】【F:ops/telemetry-dashboard/app.py†L1-L64】

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
- LLM persona voice integration ⚠️ core expedition/defection/symposium/admin flows enhanced and theory/table-talk surfaces now route through the LLM enhancer; next broaden blocklists/guard-LLM safety and codify operator guidance.
- Multi-layer press rollout ⚠️ layered coverage spans expeditions/defections/symposium/admin/mentorship flows with digest highlight blurbs and opt-in upcoming channels; next broaden template variety, add recruitment/table-talk follow-ups, and document cadence presets for operators.
- Telemetry coverage & dashboards ⚠️ all slash commands emit telemetry alongside layered-press/digest metrics and queue depth; define alert thresholds, retention windows, dispatcher instrumentation, and operator escalation guidance.
- Archive publishing automation ⚠️ scheduler exports the archive, syncs it to the container-served static host, prunes snapshots, and posts ZIP snapshots to the admin channel; document external hosting extensions and hardening guidance.
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
- **Remaining work:** migrate follow-ups and other delayed actions to the dispatcher and write dispatcher telemetry plus migration/backfill tooling for existing deployments.【F:great_work/state.py†L360-L520】

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
  - Telemetry should track order lifecycle events (enqueue, start, completion) so `/telemetry_report` can surface dispatcher health alongside the queue depth metrics already in place.
- **Future use:**
  - Follow-ups currently live in `followups`; once the dispatcher is stable, migrate them into `orders` (new `order_type='followup:defection_grudge'` etc.) to unify all delayed actions.

## 4. Sideways Discovery Mechanics – **Complete**
- Sideways discoveries map to `SidewaysEffect` payloads (faction shifts, queued conferences, opportunities).
- `_apply_sideways_effects()` handles mechanical impact and press releases.
- Tests cover effect mapping and integration.

## 5. Symposium Implementation – **Complete / Enhancement backlog**
- Weekly symposium scheduler launches topics drawn from `/symposium_propose` submissions, prunes expired entries, enforces per-player backlog caps, scores proposals for freshness/diversity before selection, spins up pledge records for every player, surfaces pledge/grace state through reminders plus `/symposium_status`, `/symposium_backlog`, and telemetry dashboards, and now carries unpaid influence forward as symposium debt before escalating to reprisals; legacy prompts only fire when the curated backlog is empty.【F:great_work/service.py†L2094-L2700】【F:great_work/telemetry.py†L788-L890】【F:great_work/discord_bot.py†L640-L780】
- **Enhancement:** expose backlog scoring insights to players, enrich long-form symposium wrap-ups once penalties resolve, and design faction-level reprisals/interest for chronic absences.

## 6. Admin Tools and Moderation – **Complete**
- `/gw_admin` group exposes reputation/influence adjustments, forced defection, and expedition cancellation with audit press.
- Permission gating enforced via Discord admin privileges.

## 7. Multi-stage Defection Arcs – **Complete**
- `/poach`, `/counter`, `/view_offers` drive negotiations with escrowed influence, follow-up scheduling, and probabilistic resolution.
- Relationship scars and contract updates applied on resolution.

## 8. Public Web Archive – **Partial**
- Static site generator produces searchable HTML, scholar profiles, timelines, and permalinks via `/export_web_archive` and `/archive_link`; Gazette scheduler now triggers automatic exports to `web_archive/`, syncs the public copy, prunes old snapshots, and publishes timestamped ZIP snapshots to the admin channel after each digest.【F:great_work/scheduler.py†L20-L180】【F:great_work/discord_bot.py†L20-L230】【F:great_work/web_archive.py†L416-L520】
- Operators have a runbook covering snapshot retention, manual export, and recovery steps (`docs/internal/ARCHIVE_OPERATIONS.md`).
- **Remaining work:** promote the runbook into external-facing docs (README/deployment guide), describe external hosting options (S3/GitHub Pages), and add production hardening guidance for the nginx container.

## 9. LLM Narrative Integration – **Partial / Safety backlog**
- `LLMClient` now orchestrates expedition launches/resolutions, defection negotiations, symposium updates, mentorship beats, theory submissions, table-talk posts, and admin notices with persona prompts, retries, pause detection, and metadata captured in press records.【F:great_work/service.py†L300-L1080】【F:great_work/service.py†L553-L704】【F:great_work/service.py†L631-L704】【F:great_work/llm_client.py†L1-L400】【F:tests/test_game_service.py†L80-L196】【F:tests/test_symposium.py†L20-L69】
- **Remaining work:** harden moderation with richer blocklists or guard-LLM review, expose configurable safety policies, and document the admin-channel pause/resume workflow for operators.

## 10. Multi-layer Press Integration – **Partial / Template backlog**
- Expedition, defection, symposium, mentorship, conference, and admin flows invoke `MultiPressGenerator`, queuing delayed gossip, faction statements, and analysis pieces that publish over time via the scheduled press queue, with digest highlights summarising upcoming drops.【F:great_work/service.py†L300-L2060】【F:great_work/multi_press.py†L1-L520】【F:great_work/state.py†L1-L220】
- **Remaining work:** add layered coverage for recruitment/table-talk outcomes, diversify long-form mentorship templates, and publish cadence presets plus tuning guidance for operators.

## 11. Telemetry and Operational Reporting – **Partial / Runbook backlog**
- Telemetry collector persists metrics in `telemetry.db`; `/telemetry_report` now includes command usage, LLM latency/failure stats, layered-press cadence summaries, digest runtimes, queue depth, and channel-level usage for every command.【F:great_work/telemetry.py†L72-L820】【F:great_work/telemetry_decorator.py†L12-L80】【F:great_work/discord_bot.py†L720-L940】
- **Remaining work:** define alert thresholds and routing, document dashboard/CLI workflows, and add dispatcher/order telemetry plus escalation guidance for operators.

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
   - Symposium announcements, votes, and resolutions ship through `_enhance_press_release`; admin tools and mentorship lifecycle events emit LLM-enhanced artefacts with layered follow-ups, and digest highlight summaries cover scheduled drops.
   - Table-talk posts and theory submissions now route through `_enhance_press_release`, but recruitment/table-talk lack layered follow-ups.
   - **Next:** extend layered coverage to recruitment/table-talk follow-ups and ensure public surfacing of reference utilities.

4. **Pause/Resume Infrastructure** – ✅ Complete
   - `GameService` tracks LLM health with exponential pause windows, admin notification queues, and `/gw_admin resume_game` unpauses once healthy.
   - Scheduler skips digests when paused and forwards status messages to the admin channel.
   - Manual resume and notification flows verified via tests and Discord command wiring.

5. **Telemetry Expansion** – ⚠️ Partial
   - Decorator shares the bot's `GameService`, emitting command usage with player context, channel metrics, LLM latency/failure telemetry, layered-press cadence, digest health, and queue depth samples.
   - `/telemetry_report` now includes queue depth summaries and alert thresholds; next, integrate dispatcher/order metrics, finish the dashboard container workflow, and agree on product-facing success KPIs.

6. **Archive Automation & Docs** – ⚠️ Partial
   - Digest scheduler now exports the web archive automatically, syncs the output into the containerised static host, posts a timestamped ZIP to the admin channel, and prunes old snapshots.
   - **Remaining:** document optional external adapters (e.g., S3), integrate the workflow into public deployment docs, and monitor storage alerts in production.

7. **Validation & Stabilisation** – ⚠️ Partial
   - Expanded tests cover LLM enhancement flows, pause triggers, and symposium outcomes.
   - **Next:** broaden smoke tests for admin pause/resume and add telemetry assertions before release.

## Current Test Coverage

- Repository defines **190** test functions across the `tests/` suite; targeted Phase 3 scenarios pass locally (`pytest tests/test_llm_client.py tests/test_service_edge_cases.py tests/test_symposium.py tests/test_game_service.py tests/test_multi_press.py tests/test_scheduler.py -q`).
- Tests cover expeditions, mentorship, conferences, offers, sideways effects, telemetry, multi-press, archive scheduling, and state edge cases.
- **Action:** wire the remaining command integration tests into CI and expand coverage for admin pause/resume plus containerised dashboard smoke tests before release.

## Testing Strategy

- Maintain unit coverage for new service methods and data-layer helpers.
- Add integration tests when wiring multi-layer press or LLM calls to prevent regressions.
- Extend snapshot checks for archive output when automated publishing is introduced.

## Success Metrics – **Partially Implemented**

- Feature completion tracking: ✅ core gameplay metrics captured via events.
- Command usage telemetry: ⚠️ partial – instrumentation spans all commands with player/channel context, layered-press counts, and digest metrics; define success thresholds and external alert routing.
- Press accessibility: ⚠️ partial – static archive syncs to the container host with retention pruning, but managed-host adapters remain optional work.
- Performance metrics: ✅ scheduler timing and command durations recorded where decorator is applied.
- Player engagement metrics (symposium participation, archive hits): ⛔ not instrumented.

## Risks & Mitigations

- **Narrative cadence gap:** Layered press now staggers drops, but recruitment and table-talk flows still ship as single beats and sideways templates remain thin; expand layered coverage before scaling content.
- **Telemetry blind spots:** Success KPI thresholds, dispatcher instrumentation, and escalation runbooks are undefined; ship these before live pilots.
- **Operational toil:** External archive hosting and config docs are still manual—automate delivery and capture deployment prerequisites for operators.

## Upcoming Focus

1. Finalise success metric targets (pause duration, engagement KPIs) and capture the telemetry escalation runbook.
2. Extend archive automation docs with container hosting instructions and optional external adapters (S3/GitHub Pages).
3. Migrate remaining follow-up queues onto the shared orders dispatcher and add dispatcher/order telemetry to `/telemetry_report`.
4. Expand layered narrative templates for recruitment/table-talk follow-ups and diversify long-form mentorship/sideways copy.
5. Publish deployment/configuration notes covering Discord channels (including highlights), telemetry dashboard container, and local LLM persona stack plus LLM safety settings.
