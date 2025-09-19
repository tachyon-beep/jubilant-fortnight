# Implementation Plan - Full Design Build

Last Updated: 2025-09-19 (Post-integration review)

## Implementation Status

- Core gameplay loops (theories, expeditions, recruitment, defection negotiations, mentorship) are live and exercised through Discord commands backed by persistence.
- Community features (symposium heartbeat, conference mechanics, admin tooling) run end to end, but supporting analytics and documentation lag behind.
- Narrative polish pillars (multi-layer press, persona-driven copy, automated archive publishing) remain partially integrated and are the focus of the next iteration.

## Infrastructure Utilization

1. **Offers Table** – ✅ Actively used for poach/counter offer chains with follow-up scheduling.【F:great_work/state.py†L208-L362】【F:great_work/service.py†L520-L760】
2. **Follow-ups System** – ✅ Drives negotiation deadlines, grudge timers, and sideways opportunities.【F:great_work/state.py†L344-L420】【F:great_work/service.py†L1996-L2059】
3. **Defection Logic** – ✅ Exposed via `/poach`, `/counter`, `/view_offers` and resolves probabilistically with scars and relationship updates.【F:great_work/discord_bot.py†L294-L458】【F:great_work/service.py†L572-L760】
4. **Career Progression** – ✅ Mentorship queue and lab assignment commands progress scholars during digests.【F:great_work/service.py†L1024-L1105】【F:great_work/service.py†L1934-L1995】
5. **Press Templates** – ⚠️ Still single-release; `MultiPressGenerator` is not yet wired into live flows.【F:great_work/service.py†L170-L392】【F:great_work/multi_press.py†L1-L497】
6. **Event Sourcing** – ✅ Append-only event log covers all major actions and exports via `/export_log`.【F:great_work/state.py†L18-L170】【F:great_work/discord_bot.py†L577-L637】
7. **Influence System** – ✅ Five-dimensional influence with reputation caps governs costs and rewards.【F:great_work/service.py†L677-L835】
8. **Telemetry Pipeline** – ⚠️ Collector exists, but only a subset of commands emit metrics and the decorator drops player context because it instantiates `GameService()` without parameters.【F:great_work/telemetry.py†L12-L320】【F:great_work/telemetry_decorator.py†L12-L62】

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
- LLM persona voice integration ⛔ outstanding (client present, not wired)
- Multi-layer press rollout ⚠️ outstanding (generator unused)
- Telemetry coverage & dashboards ⚠️ partially wired
- Archive publishing automation ⛔ not started
- Documentation pass for deployment/config ⚠️ pending

## 1. Mentorship System and Scholar Careers – **Complete**
- Player-driven mentorship queue with `/mentor`, lab assignment with `/assign_lab`.
- Mentorships persist in `mentorships` table and activate during digests.
- Tests cover queue/resolve logic and press output.

## 2. Conference Mechanics – **Complete**
- `/conference` launches debates, `resolve_conferences()` adjudicates outcomes with reputation deltas.
- Conferences stored in `conferences` table and resolved during digests.
- Press and events emitted on launch and resolution.

## 3. Generic Order Batching Infrastructure – **In Progress**
- Mentorships and conferences batch via bespoke tables; follow-ups handle negotiations.
- **Remaining work:** introduce a shared `orders` table and dispatcher to avoid future bespoke queues, add indexes on scheduling columns, and migrate existing flows onto the shared pipeline.【F:great_work/state.py†L18-L141】

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
- Static site generator produces searchable HTML, scholar profiles, timelines, and permalinks via `/export_web_archive` and `/archive_link`.
- **Remaining work:** automate publishing (e.g., attach archive to Discord or push to hosting) and document operational workflow.【F:great_work/web_archive.py†L416-L520】

## 9. LLM Narrative Integration – **Not Integrated**
- `LLMClient` provides persona prompting, retries, and fallback templates; unit tests validate behaviour.
- **Remaining work:** invoke the client from press generation, populate moderator blocklists, wire batch generation for digests, and gate outputs behind safety checks.【F:great_work/llm_client.py†L1-L283】

## 10. Multi-layer Press Integration – **Not Integrated**
- `MultiPressGenerator` defines layered coverage logic; tests exercise scenarios.
- **Remaining work:** select coverage depth per event, enqueue layered releases into digests, and reconcile with archive ordering.【F:great_work/multi_press.py†L1-L497】

## 11. Telemetry and Operational Reporting – **Partial**
- Telemetry collector persists metrics in `telemetry.db`; `/telemetry_report` renders summaries.
- **Remaining work:** decorate all game-impacting commands, fix decorator instantiation (inject service instead of creating `GameService()`), add channel-level usage metrics, and ensure gauges exist for archive exports and digest runtimes.【F:great_work/telemetry_decorator.py†L12-L62】【F:great_work/discord_bot.py†L668-L736】

## Current Test Coverage

- Repository defines **186** test functions across the `tests/` suite; `pytest` execution currently fails in this environment because the runner is not installed (`pytest: command not found`).
- Tests cover expeditions, mentorship, conferences, offers, sideways effects, telemetry, multi-press, and state edge cases.
- **Action:** add `pytest` to the bootstrap instructions (e.g., `make install`) and re-run the suite after integrating narrative layers.

## Testing Strategy

- Maintain unit coverage for new service methods and data-layer helpers.
- Add integration tests when wiring multi-layer press or LLM calls to prevent regressions.
- Extend snapshot checks for archive output when automated publishing is introduced.

## Success Metrics – **Partially Implemented**

- Feature completion tracking: ✅ core gameplay metrics captured via events.
- Command usage telemetry: ⚠️ partial – decorator coverage incomplete, player context missing.
- Press accessibility: ⚠️ partial – static archive exists locally but lacks automated distribution.
- Performance metrics: ✅ scheduler timing and command durations recorded where decorator is applied.
- Player engagement metrics (symposium participation, archive hits): ⛔ not instrumented.

## Risks & Mitigations

- **Narrative quality gap:** Multi-layer press and persona voice remain unused; prioritize integration before expanding content scope.
- **Telemetry blind spots:** Extend instrumentation prior to live pilots to avoid operating without usage data.
- **Operational toil:** Without automated archive publishing and config docs, deployments rely on manual intervention—document in the next docs pass.

## Upcoming Focus

1. Wire `MultiPressGenerator` into expedition, defection, and symposium flows; adjust archive/export to respect layered releases.
2. Integrate `LLMClient` for optional persona copy with safe fallbacks and moderation lists.
3. Introduce a shared `orders` table and migrate mentorship/conference scheduling onto it.
4. Expand telemetry coverage and repair the decorator to accept injected services.
5. Automate archive publishing and document environment configuration for operators.
