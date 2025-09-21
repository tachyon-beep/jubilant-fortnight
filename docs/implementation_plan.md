# Implementation Plan - Full Design Build

Last Updated: 2025-09-21 (Guardian moderation, seasonal telemetry)

## Implementation Status

- Core gameplay loops (theories, expeditions, recruitment, defection negotiations, mentorship) remain stable and exercised through Discord commands backed by persistence.
- LLM-enhanced multi-layer press now powers expeditions, defection negotiations, symposium calls, mentorship beats, recruitment briefs, table-talk digests, and admin interventions while maintaining template fallbacks.
- Mentorship lifecycles and admin pause/resume flows schedule layered follow-ups, deliver dual-paced fast/long drops, surface “upcoming highlights” to opt-in channels, and publish digest highlight blurbs drawn from the scheduled press queue alongside admin notifications.
- Tone packs and YAML libraries rotate recruitment/table-talk headlines, blurbs, and callouts; the new sidecast arcs, defection epilogues, sideways vignette catalogue, and narrative writing guide feed dispatcher-scheduled press and orders tagged for operations follow-up while keeping persona alignment in reach.【F:great_work/data/sidecast_arcs.yaml†L1-L90】【F:great_work/data/defection_epilogues.yaml†L1-L48】【F:great_work/data/sideways_vignettes.yaml†L1-L180】【F:docs/WRITING_GUIDE.md†L1-L120】
- Telemetry dashboards (Discord report + bundled FastAPI dashboard) and containerised archive hosting are in place; the `/telemetry_report` health summary now evaluates digest runtime, release floors, queue depth, dispatcher backlog, LLM latency/failure, and symposium/seasonal/contract debt, and digest exports mirror into GitHub Pages alongside local hosting.
- Dispatcher backlog alerts now schedule symposium reprimand follow-ups, post admin notifications, and can be managed through `/gw_admin list_orders` and `/gw_admin cancel_order` for live-ops intervention.
- Recruitment odds are now exposed via `/recruit_odds`, listing faction modifiers, cooldown penalties, and influence bonuses so players can compare bids before committing.
- Contract upkeep now drains influence every digest, automatically recording contract debt and reprisals when players fall behind; `/status` surfaces per-faction upkeep and outstanding balances.
- Faction investments (`/invest`) and archive endowments (`/endow_archive`) provide player-facing long-tail influence sinks that feed relationship boosts, debt relief, and reputation rewards while logging telemetry/press for operations review.【F:great_work/service.py†L1160-L4490】【F:great_work/discord_bot.py†L883-L1607】【F:tests/test_influence_sinks.py†L1-L88】
- Symposium backlog/status commands now expose scoring breakdowns (age decay, fresh bonus, repeat penalty) and debt reprisal schedules so players and operators can audit the weekly loop; telemetry mirrors the same components for tuning.【F:great_work/service.py†L3350-L3590】【F:great_work/discord_bot.py†L789-L904】【F:tests/test_symposium.py†L400-L470】

## Infrastructure Utilization

1. **Offers Table** – ✅ Actively used for poach/counter offer chains with follow-up scheduling.【F:great_work/state.py†L208-L362】【F:great_work/service.py†L520-L760】
2. **Follow-ups System** – ✅ All delayed actions (mentorship activations, offer deadlines, symposium reminders, reprimands) now flow through the shared dispatcher orders after automatically migrating legacy followups.【F:great_work/state.py†L344-L720】【F:great_work/service.py†L1996-L4360】
3. **Defection Logic** – ✅ Exposed via `/poach`, `/counter`, `/view_offers` and resolves probabilistically with scars and relationship updates.【F:great_work/discord_bot.py†L294-L458】【F:great_work/service.py†L572-L760】
4. **Career Progression** – ✅ Mentorship queue and lab assignment commands progress scholars during digests.【F:great_work/service.py†L1024-L1105】【F:great_work/service.py†L1934-L1995】
5. **Press Templates** – ⚠️ `MultiPressGenerator` drives expedition, defection, symposium, mentorship, recruitment, table-talk, sidecast, conference, and admin narratives with scheduled follow-ups and dual cadence presets; tone packs randomise headlines/blurbs and the expanded YAML libraries feed recruitment/table-talk/sidecast/defection epilogue layers while the sideways catalogue dispatches narrative vignettes. Mentorship/sidecast history now surfaces in `/status`, recruitment odds, defection negotiations, seasonal commitments, and faction projects; Guardian moderation now guards both player input and generated press. Remaining work focuses on pushing informational commands to public channels and exploring which future unlocks should respond to accumulated relationship deltas.【F:great_work/service.py†L170-L4700】【F:great_work/multi_press.py†L620-L1120】【F:great_work/data/recruitment_press.yaml†L1-L48】【F:great_work/data/table_talk_press.yaml†L1-L24】【F:great_work/data/sidecast_arcs.yaml†L1-L90】【F:great_work/data/defection_epilogues.yaml†L1-L48】【F:great_work/data/sideways_vignettes.yaml†L1-L180】【F:great_work/press_tone.py†L1-L160】【F:great_work/moderation.py†L1-L240】
6. **Event Sourcing** – ✅ Append-only event log covers all major actions and exports via `/export_log`.【F:great_work/state.py†L18-L170】【F:great_work/discord_bot.py†L577-L637】
7. **Influence System** – ✅ Five-dimensional influence with reputation caps governs costs and rewards.【F:great_work/service.py†L677-L835】
8. **Telemetry Pipeline** – ⚠️ Collector ingests metrics from every slash command plus layered-press cadence, digest runtimes, queue depth, dispatcher backlog snapshots, and LLM latency; Discord `/telemetry_report` now adds a health summary driven by configurable thresholds while the bundled FastAPI dashboard surfaces historical aggregates. Remaining work covers external alert routing, CSV/JSON exports for dispatcher audits, and richer moderator dashboards that surface order filters and backlog trends.【F:great_work/telemetry.py†L72-L1110】【F:great_work/telemetry_decorator.py†L12-L80】【F:great_work/discord_bot.py†L786-L1475】【F:ops/telemetry-dashboard/app.py†L1-L174】

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
- LLM persona voice integration ⚠️ core expedition/defection/symposium/admin flows enhanced and theory/table-talk surfaces now route through the LLM enhancer; Guardian moderation is live, with next steps focused on calibration tooling and operator guidance.
- Multi-layer press rollout ⚠️ layered coverage now spans expeditions/defections/symposium/mentorship/recruitment/table-talk/sidecasts with digest highlight blurbs and opt-in upcoming channels; sideways vignettes dispatch layered follow-ups, bespoke landmark prep briefs now accompany landmark outcomes, and remaining work focuses on cadence tuning.
- Telemetry coverage & dashboards ⚠️ all slash commands emit telemetry alongside layered-press/digest metrics, queue depth, and dispatcher backlog snapshots; alert thresholds and the operator runbook now ship via the `/telemetry_report` health summary, with remaining work focused on retention windows, external escalation guidance, and richer dispatcher analytics.
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
- **Remaining work:** promote the runbook into external-facing docs (README/deployment guide), document the GitHub Pages publishing workflow we’ve standardised on, and add production hardening guidance for the nginx container.

## 9. LLM Narrative Integration – **Partial / Safety backlog**
   - `LLMClient` now orchestrates expedition launches/resolutions, defection negotiations, symposium updates, mentorship beats, theory submissions, table-talk posts, and admin notices with persona prompts, retries, pause detection, and metadata captured in press records.【F:great_work/service.py†L300-L1080】【F:great_work/service.py†L553-L704】【F:great_work/service.py†L631-L704】【F:great_work/llm_client.py†L1-L400】【F:tests/test_game_service.py†L80-L196】【F:tests/test_symposium.py†L20-L69】
   - **Remaining work:** calibrate Guardian categories/thresholds, surface moderation override tooling for operators, and expand the pause/resume playbook around LLM failures.

## 10. Multi-layer Press Integration – **Partial / Template backlog**
   - Expedition, defection, symposium, mentorship, conference, recruitment, table-talk, sidecast, and admin flows invoke `MultiPressGenerator`, queuing delayed gossip, faction statements, and analysis pieces that publish over time via the scheduled press queue, with digest highlights summarising upcoming drops.【F:great_work/service.py†L300-L2470】【F:great_work/multi_press.py†L320-L1120】【F:great_work/state.py†L344-L720】
   - **Remaining work:** extend layered mentorship beats with stateful consequences (scars, loyalty swings) and continue tuning cadence presets for the expanded vignette/tag mechanics.

## 11. Telemetry and Operational Reporting – **Partial / Runbook backlog**
   - Telemetry collector persists metrics in `telemetry.db`; `/telemetry_report` now includes command usage, LLM latency/failure stats, layered-press cadence summaries, digest runtimes, queue depth, channel-level usage, investment/endowment analytics, and seasonal commitment debt snapshots.【F:great_work/telemetry.py†L72-L1504】【F:great_work/telemetry_decorator.py†L12-L80】【F:great_work/discord_bot.py†L720-L1637】
   - Calibration snapshots now run after each digest (optional via `GREAT_WORK_CALIBRATION_SNAPSHOTS`), `/gw_admin calibration_snapshot` uploads the latest JSON, `python -m great_work.tools.export_calibration_snapshot` + `...generate_sample_telemetry` support offline analysis, and the telemetry dashboard surfaces the latest totals with a raw `/api/calibration_snapshot` endpoint.【F:great_work/analytics/calibration.py†L1-L244】【F:great_work/scheduler.py†L29-L210】【F:great_work/discord_bot.py†L2260-L2333】【F:ops/telemetry-dashboard/app.py†L1-L230】
   - **Remaining work:** tune thresholds/knobs once live telemetry arrives (calibrate seasonal costs, investment incentives, symposium heuristics) and fold the results into the ops playbook.

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
   - Symposium announcements, votes, and resolutions ship through `_enhance_press_release`; admin tools, mentorship lifecycle events, recruitment outcomes, table-talk posts, and sidecasts emit LLM-enhanced artefacts with layered follow-ups, and digest highlight summaries cover scheduled drops.
   - `/gw_admin list_orders` and `/gw_admin cancel_order` now expose dispatcher backlogs from Discord, backed by telemetry snapshots.
   - Informational commands (`/status`, `/symposium_status`, `/symposium_proposals`, `/symposium_backlog`, `/wager`, `/seasonal_commitments`, `/faction_projects`, `/gazette`, `/export_log`) now publish to the configured channels while preserving ephemeral replies; player status surfaces faction sentiment derived from persisted mentorship/sidecast memories so players and ops can audit relationship deltas.
   - Narrative validation CLI (`python -m great_work.tools.validate_narrative --all`) enforces structure, and the preview CLI (`python -m great_work.tools.preview_narrative`) renders sample output across tone packs, press modules, sidecasts, epilogues, and vignettes; Makefile & guides document both workflows.
   - **Next:** optional—extend previews with richer persona permutations or per-surface Markdown exports once contributors request them.

4. **Pause/Resume Infrastructure** – ✅ Complete
   - `GameService` tracks LLM health with exponential pause windows; repeated failures auto‑pause the game and `/gw_admin resume_game` unpauses once healthy.
   - Scheduler skips digests when paused and forwards status messages to the admin channel.
   - `/gw_admin pause_game` now mirrors the resume flow, archiving an admin press release, emitting layered notifications, and tracking telemetry so operators can proactively halt play before resuming. Tests cover manual pause + resume transitions.【F:great_work/service.py†L5197-L5263】【F:great_work/discord_bot.py†L2223-L2255】【F:tests/test_service_edge_cases.py†L120-L147】

5. **Telemetry Expansion** – ⚠️ Partial
   - Decorator shares the bot's `GameService`, emitting command usage with player context, channel metrics, LLM latency/failure telemetry, layered-press cadence, digest health, queue depth, and the new symposium/economy guardrails.
   - `/telemetry_report` highlights health checks, symposium scoring/debt, long-tail economy summaries, seasonal commitment debt warnings, and the new product KPIs (active players, manifesto adoption, archive reach); alerts fan out to all configured webhooks/email endpoints with cooldowns, the dashboard adds dispatcher filters plus CSV export, economy summaries surface outstanding commitments, and both surfaces chart daily KPI history for the last month with percentile summaries and sparkline charts via Chart.js.
   - Canonical KPI targets are now stored in `telemetry.db`, override alert thresholds automatically, and the dashboard presents engagement cohorts (new vs returning players) plus symposium-participation rollups so ops can compare adoption against targets while monitoring live command mixes.
   - **Next:** add automated exports for cohort summaries and long-term KPI snapshots to support post-playtest analysis.

6. **Archive Automation & Docs** – ✅ Complete
   - Digest scheduler now exports the web archive automatically, syncs the output into the containerised static host, mirrors the build into a configured GitHub Pages repository (dropping `.nojekyll`), posts a timestamped ZIP to the admin channel, prunes old snapshots, and alerts when snapshot storage crosses configurable thresholds. Operator guides describe the Pages workflow and storage runbook.

7. **Validation & Stabilisation** – ⚠️ Partial
   - Expanded tests cover LLM enhancement flows, pause triggers, and symposium outcomes.
   - **Next:** broaden smoke tests for admin pause/resume and add telemetry assertions before release.

## Current Test Coverage

- Repository defines **227** test functions across the `tests/` suite; targeted Phase 3 scenarios pass locally (`pytest tests/test_llm_client.py tests/test_service_edge_cases.py tests/test_symposium.py tests/test_game_service.py tests/test_multi_press.py tests/test_scheduler.py -q`).
- Tests cover expeditions, mentorship, conferences, offers, sideways effects, telemetry, multi-press, archive scheduling, and state edge cases.
- **Action:** wire the remaining command integration tests into CI and expand coverage for admin pause/resume plus containerised dashboard smoke tests before release.

## Testing Strategy

- Maintain unit coverage for new service methods and data-layer helpers.
- Add integration tests when wiring multi-layer press or LLM calls to prevent regressions.
- Extend snapshot checks for archive output when automated publishing is introduced.

## Success Metrics – **Partially Implemented**

- Feature completion tracking: ✅ core gameplay metrics captured via events.
- Command usage telemetry: ⚠️ partial – instrumentation spans all commands with player/channel context, layered-press counts, and digest metrics; next calibrate the KPI thresholds and ensure dashboards/alert feeds reach the on-call rotation.
- Press accessibility: ✅ static archive syncs to the container host, mirrors into GitHub Pages, prunes history, and raises alerts when storage pressure mounts.
- Performance metrics: ✅ scheduler timing and command durations recorded where decorator is applied.
- Player engagement metrics (symposium participation, archive lookups, nickname adoption, press shares): ✅ instrumented and visible in `/telemetry_report` and the dashboard.

## Risks & Mitigations

- **Narrative cadence gap:** Layered press now staggers drops across recruitment, defection, sidecasts, and sideways vignettes; continue enriching the vignette catalogue and documenting tone-pack guardrails before scaling content.
- **Telemetry blind spots:** External escalation routing is still pending; default thresholds and the telemetry runbook now cover digest runtime, queue depth, dispatcher backlog, and LLM health.
- **Operational toil:** GitHub Pages publishing now mirrors exports automatically, yet operators still need rotation ownership around archive publishing and Guardian moderation; document handoffs before pilots.

## Upcoming Focus

1. Use the new guardrails to collect telemetry on seasonal commitments, faction projects, investments, and archive endowments; feed real-world observations back into the runbook and dashboard tuning ahead of 1.0 playtests.
2. Tune the new long‑tail sinks (faction investments, archive endowments): balance costs/rewards, wire telemetry guardrails, and tie symposium debt escalation into these systems.
3. Finalise telemetry/ops guardrails: tune the KPI thresholds, integrate alert webhooks with the on-call tooling, and extend dispatcher dashboards with richer historical comparisons (sparklines, percentile bands).
4. Tune seasonal commitment and faction project defaults using the new telemetry + calibration helpers; document recommended ranges ahead of playtests.
