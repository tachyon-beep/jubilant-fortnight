# Gap Analysis: High-Level Design vs. Current Implementation

Last Updated: 2025-09-27 (Phase 3 telemetry & narrative refresh)

## 1. Scholar Lifecycle and Memory

- **Design intent:** Maintain a roster of 20–30 memorable scholars blending handcrafted legends with procedurally generated additions, spawn sidecast scholars from expeditions, nurture mentorship-driven career growth, and track defections with scars and public fallout.【F:docs/HLD.md†L24-L177】
- **Implementation status:** `GameService` enforces the roster window, seeds new procedurally generated scholars, activates mentorships, progresses mentored careers, and resolves multi-stage defection negotiations with multi-layer press and persona metadata archived alongside outcomes. Mentorship queue, activation, and completion flows now schedule fast and long-form follow-ups via `MultiPressGenerator` to match the documented cadence.【F:great_work/service.py†L89-L760】【F:great_work/service.py†L1024-L1995】【F:great_work/multi_press.py†L420-L624】
- **Gap:** Sidecasts still land as a single gossip artefact with no follow-on scenes, and mentorship arcs lack persistent scars or relationship shifts beyond their layered announcements.【F:great_work/service.py†L2254-L2287】【F:great_work/press.py†L20-L145】

## 2. Confidence Wagers, Reputation, and Recruitment Effects

- **Design intent:** Confidence wagers must follow the tuned reward/penalty table, clamp reputation within bounds, and impose recruitment cooldowns on high-stakes wagers while recruitment odds reflect cooldowns, faction influence, and unlock thresholds.【F:docs/HLD.md†L44-L138】
- **Implementation status:** Theory and expedition commands require explicit confidence levels; resolutions apply wager tables, clamp reputation, enforce cooldowns, and recruitment odds include influence bonuses plus cooldown penalties, all surfaced through `/status`, `/wager`, and the new `/recruit_odds` preview table.【F:great_work/service.py†L1009-L1110】【F:great_work/discord_bot.py†L317-L381】
- **Gap:** None – players can review comparative recruitment odds before committing via `/recruit_odds`.

## 3. Expedition Structure and Outcomes

- **Design intent:** Each expedition type should apply tailored costs, prep modifiers, and depth-aware failure tables that yield sideways discoveries with gameplay repercussions such as faction swings, gossip, or queued orders.【F:docs/HLD.md†L57-L138】
- **Implementation status:** Expedition launches deduct faction influence, persist preparation details, and an `ExpeditionResolver` rolls d100, applies modifiers, consults depth-specific failure tables, and emits sideways effects that can spawn theories, shift factions, or schedule follow-ups.【F:great_work/service.py†L170-L392】【F:great_work/expeditions.py†L60-L135】【F:great_work/models.py†L122-L206】【F:great_work/service.py†L2090-L2248】
- **Gap:** Landmark preparation still resolves to a single block of text, and sideways effect mappings are hard-coded templates rather than data-driven, limiting variability against the design’s call for bespoke deep-prep vignettes.【F:docs/HLD.md†L90-L138】【F:great_work/expeditions.py†L124-L213】

### 3.1 Great Projects - Status

- **Design intent:** Full implementation of Great Projects as large science efforts that unlock new research domains.【F:docs/HLD.md†L61】
- **Implementation status:** Great Projects are selectable via Discord, carry bespoke costs and rewards, and resolve through the shared expedition pipeline.【F:great_work/service.py†L170-L214】【F:great_work/discord_bot.py†L141-L209】【F:great_work/data/settings.yaml†L18-L28】
- **Gap:** None – feature matches the high-level design.

## 4. Influence Economy and Faction Mechanics

- **Design intent:** Influence should operate as a five-dimensional economy with soft caps tied to reputation and faction requirements across key actions, supported by additional sinks such as symposium commitments and contracts.【F:docs/HLD.md†L90-L213】
- **Implementation status:** Influence is stored per faction, clamps to reputation-derived caps, and is spent/earned by expeditions, recruitment, poach/counter offers, symposium pledges, and contract upkeep; `/status` now lists ongoing contract costs alongside caps and thresholds.【F:great_work/state.py†L18-L520】【F:great_work/service.py†L677-L1110】【F:great_work/service.py†L3200-L3470】【F:great_work/discord_bot.py†L780-L820】
- **Gap:** Seasonal commitments and other long-tail sinks (e.g., faction projects) still need to be wired up so players make broader economic trade-offs beyond scholar contracts.【F:docs/HLD.md†L126-L213】

## 5. Press Artefacts and Public Record

- **Design intent:** Every move should produce persona-driven press artefacts that persist in a public archive—bulletins, manifestos, discoveries, retractions, gossip, recruitment notes, defection wires—and stay publicly accessible.【F:docs/HLD.md†L86-L354】
- **Implementation status:** Core actions call structured template generators, archive releases in SQLite, and `/gazette`, `/export_log`, and `/export_web_archive` surface history. Expedition, defection, symposium, mentorship, and admin flows queue delayed follow-ups via `MultiPressGenerator`, with staggered fast/long cadences delivering gossip, faction statements, mentorship bulletins, and administrative updates alongside the primary artefact; theory submissions and table-talk updates now run through the LLM enhancer before archiving, and digest ticks mint highlight blurbs from the scheduled press queue.【F:great_work/service.py†L170-L1400】【F:great_work/service.py†L220-L340】【F:great_work/service.py†L553-L704】【F:great_work/service.py†L631-L704】【F:great_work/multi_press.py†L1-L680】【F:great_work/state.py†L1-L520】【F:great_work/discord_bot.py†L562-L940】【F:great_work/web_archive.py†L416-L520】
- **Gap:** Recruitment and table-talk flows still publish only a single beat with no layered follow-ups, layered template variety for long-running mentorship arcs remains thin, and sideways effect mappings stay hard-coded instead of data-driven, limiting narrative diversity against the design brief.【F:great_work/service.py†L900-L1006】【F:great_work/service.py†L2830-L3058】【F:great_work/multi_press.py†L180-L360】【F:docs/HLD.md†L90-L213】

### 5.1 Public archive availability

- **Design intent:** Keep a permanent, public, citable archive beyond Discord.【F:docs/HLD.md†L214-L354】
- **Implementation status:** `/export_web_archive` builds a static site with permalinks, search, and scholar profiles on disk, `/archive_link` retrieves specific headlines, each digest exports the archive automatically, syncs it into the container-served static host, and posts a timestamped ZIP snapshot to the admin channel with retention pruning.【F:great_work/discord_bot.py†L591-L737】【F:great_work/service.py†L1747-L1880】【F:great_work/scheduler.py†L20-L180】【F:docs/internal/ARCHIVE_OPERATIONS.md†L1-L130】
- **Gap:** External hosting adapters (S3, GitHub Pages) remain manual, and the containerised nginx service still needs production hardening and monitoring guidance.【F:docs/HLD.md†L214-L354】【F:great_work/scheduler.py†L20-L180】

## 6. Timing, Gazette Cadence, and Symposiums

- **Design intent:** Twice-daily Gazette digests should advance cooldowns, timeline years, and queued orders before publishing to Discord, while weekly symposiums run structured topics with mandatory responses.【F:docs/HLD.md†L101-L386】
- **Implementation status:** `GazetteScheduler` advances the digest, resolves follow-ups/mentorships/conferences, exports the archive, posts to configured channels, emits digest highlight blurbs drawn from the scheduled press queue, raises alerts on slow or thin digests, and sends "upcoming highlights" to an opt-in channel. Weekly symposia now auto-expire stale proposals, enforce per-player backlog caps, score pending topics for freshness/diversity, create pledge rows for every player, settle outstanding symposium debt before new pledges, trigger faction reprisals on sustained debt, and surface pledge/grace state plus ranking data through reminders, `/symposium_status`, `/symposium_backlog`, and telemetry dashboards.【F:great_work/scheduler.py†L20-L200】【F:great_work/service.py†L2094-L2700】【F:great_work/telemetry.py†L788-L890】【F:great_work/discord_bot.py†L640-L780】
- **Gap:** Debt tracking and auto-settlement land influence penalties, but the economy still lacks faction-level reprisals or longer-tail consequences for repeated absences, and proposal scoring still relies on tunable heuristics without player-facing transparency. Iterate on escalation levers and explain selection weighting before live pilots.【F:great_work/service.py†L2141-L2700】【F:docs/internal/PHASE3_POLISH_DESIGN.md†L1-L120】

### 6.1 Non-expedition order batching

- **Design intent:** Orders like mentorships, conferences, and other delayed actions should share a generic batching framework handled at digest time.【F:docs/HLD.md†L101-L213】
- **Implementation status:** A shared `orders` table now feeds dispatcher helpers that activate mentorships and resolve conferences during the digest tick, while the legacy tables persist for history.【F:great_work/state.py†L360-L520】【F:great_work/service.py†L1360-L2060】
- **Gap:** Follow-up queues and other delayed hooks still bypass the dispatcher, and there is no backfill/migration tooling or telemetry to monitor the shared orders backlog, keeping onboarding for new order types brittle.【F:great_work/state.py†L344-L520】【F:great_work/service.py†L1996-L2059】

## 7. Data Model and Persistence

- **Design intent:** Persist players, scholars, relationships, theories, expeditions, offers, press artefacts, and events with exports available through a bot command.【F:docs/HLD.md†L203-L385】
- **Implementation status:** SQLite schema covers all major entities including offers, mentorships, conferences, symposium topics/votes, and press; the new `orders` table centralises delayed work (mentorship activations, conference resolutions) consumed by the dispatcher, while exports flow through `/export_log` and archive tooling.【F:great_work/state.py†L18-L520】【F:great_work/service.py†L1402-L1880】【F:great_work/discord_bot.py†L562-L737】
- **Gap:** Follow-up queues still sit outside the dispatcher, and there is no migration script or index tuning for existing deployments—adopting the shared orders pipeline requires backfill tooling and operational guidance.【F:great_work/state.py†L360-L520】

## 8. Discord Command Surface and Admin Tools

- **Design intent:** Provide slash commands for theories, wagers, recruitment, expeditions, conferences, status checks, log exports, and admin hotfixes, with telemetry on usage.【F:docs/HLD.md†L248-L386】
- **Implementation status:** Commands cover the expected surface, including `/poach`, `/counter`, `/view_offers`, `/mentor`, `/assign_lab`, `/conference`, `/export_web_archive`, `/telemetry_report`, and `/gw_admin` subcommands for moderation. All commands now share the telemetry decorator, emitting player, channel, success metrics, layered-press counts, and digest health; operators can review stats via Discord or the bundled telemetry dashboard container.【F:great_work/discord_bot.py†L123-L940】【F:great_work/telemetry_decorator.py†L12-L80】【F:great_work/telemetry.py†L72-L660】【F:ops/telemetry-dashboard/app.py†L1-L64】
- **Gap:** Several information surfaces still return ephemeral responses (table-talk summary, theory references), and success-metric thresholds for alerts are not yet tuned to product expectations.【F:great_work/discord_bot.py†L523-L940】【F:great_work/telemetry.py†L600-L660】

### 8.1 Credentials and application configuration

- **Design intent:** Document the runtime configuration (token, app id, channel routing) required to deploy the bot.【F:docs/HLD.md†L248-L286】
- **Implementation status:** The bot reads environment variables for IDs and channel routing, but the design docs still omit a deployment appendix describing the expected configuration.【F:great_work/discord_bot.py†L69-L113】
- **Gap:** Add a short configuration section to docs so operators understand required environment variables and channel mapping.

## 9. LLM and Narrative Integration

- **Design intent:** Generate press and reactions through persona-driven LLM prompts with batching and safety controls.【F:docs/HLD.md†L318-L369】
- **Implementation status:** The LLM client now drives expeditions, defection negotiations, symposium updates, mentorship beats, theory submissions, table-talk posts, and admin notices with persona metadata, retry scheduling, and blocklist safeguards; layered press metrics feed telemetry and tests run in mock mode to verify prompts and pause behaviour.【F:great_work/service.py†L300-L1080】【F:great_work/service.py†L553-L704】【F:great_work/service.py†L631-L704】【F:great_work/llm_client.py†L1-L240】【F:tests/test_game_service.py†L80-L196】【F:tests/test_symposium.py†L20-L69】
- **Gap:** The moderation layer is still limited to a static word list, there's no secondary guard-LLM or redaction workflow, and operator-facing pause/resume runbooks remain undocumented outside internal planning notes.【F:great_work/llm_client.py†L40-L140】【F:docs/HLD.md†L318-L369】

## Summary of Major Gaps

1. Recruitment/table-talk flows still publish single-beat coverage and layered templates remain thin for long mentorship arcs and sideways discoveries, limiting the narrative variety called for in the design.
2. Influence sinks remain limited to expeditions and poaching, leaving symposium commitments and longer-term obligations unimplemented.
3. Symposium proposals are player-driven with automated expiries, scoring heuristics, and pledge penalties/debt carryover; remaining work is sharper economic escalation (faction reprisals, interest) and transparent backlog curation reports before launch.
4. Telemetry dashboards and `/telemetry_report` now surface queue depth and digest health, but success KPI thresholds, escalation routing, and dispatcher instrumentation still need to be defined and documented for operators.
5. Static archives auto-export, sync to the container host, and prune snapshots; external hosting adapters and production monitoring guidance for the nginx container remain outstanding.
