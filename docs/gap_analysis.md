# Gap Analysis: High-Level Design vs. Current Implementation

Last Updated: 2025-09-30 (Sidecast arcs, defection epilogues, dispatcher console)

## 1. Scholar Lifecycle and Memory

- **Design intent:** Maintain a roster of 20–30 memorable scholars blending handcrafted legends with procedurally generated additions, spawn sidecast scholars from expeditions, nurture mentorship-driven career growth, and track defections with scars and public fallout.【F:docs/HLD.md†L24-L177】
- **Implementation status:** `GameService` enforces the roster window, seeds new procedurally generated scholars, activates mentorships, progresses mentored careers, and resolves multi-stage defection negotiations with layered press. Multi-press orchestration now pulls from the sidecast arc catalogue, defection epilogues, recruitment/table-talk follow-ups, and sideways vignette payloads so sidecasts advance through debut/integration/spotlight beats while defections apply relationship adjustments alongside archived outcomes.【F:great_work/service.py†L89-L760】【F:great_work/service.py†L1024-L1995】【F:great_work/service.py†L4460-L4668】【F:great_work/multi_press.py†L350-L520】【F:great_work/multi_press.py†L900-L1120】【F:great_work/data/sidecast_arcs.yaml†L1-L90】【F:great_work/data/defection_epilogues.yaml†L1-L48】
- **Gap:** Mentorship activations/progression/completion now adjust scholar feelings and log history, sidecast phases persist sponsor ties, `/status` surfaces the summary, recruitment/defection flows pull in the modifier, and the new seasonal commitments and faction projects consume the same history. Fresh defaults (28-day pledges, relationship-weighted costs, seasonal debt reprisal knobs) and `/gw_admin create/update` controls give operators levers to tune the loops in real time. Remaining work is data-driven balancing and telemetry hooks that flag overdue commitments before reprisal cascades.【F:great_work/service.py†L3717-L3912】【F:great_work/service.py†L4205-L4376】【F:great_work/discord_bot.py†L1582-L1669】【F:great_work/state.py†L2188-L2416】

## 2. Confidence Wagers, Reputation, and Recruitment Effects

- **Design intent:** Confidence wagers must follow the tuned reward/penalty table, clamp reputation within bounds, and impose recruitment cooldowns on high-stakes wagers while recruitment odds reflect cooldowns, faction influence, and unlock thresholds.【F:docs/HLD.md†L44-L138】
- **Implementation status:** Theory and expedition commands require explicit confidence levels; resolutions apply wager tables, clamp reputation, enforce cooldowns, and recruitment odds include influence bonuses plus cooldown penalties, all surfaced through `/status`, `/wager`, and the new `/recruit_odds` preview table.【F:great_work/service.py†L1009-L1110】【F:great_work/discord_bot.py†L317-L381】
- **Gap:** None – players can review comparative recruitment odds before committing via `/recruit_odds`.

## 3. Expedition Structure and Outcomes

- **Design intent:** Each expedition type should apply tailored costs, prep modifiers, and depth-aware failure tables that yield sideways discoveries with gameplay repercussions such as faction swings, gossip, or queued orders.【F:docs/HLD.md†L57-L138】
- **Implementation status:** Expedition launches deduct faction influence, persist preparation details, and an `ExpeditionResolver` rolls d100, applies modifiers, consults depth-specific failure tables, and now draws from a data-driven sideways catalogue to emit faction shifts, theories, queued orders, and tagged follow-ups that the dispatcher applies downstream.【F:great_work/service.py†L170-L392】【F:great_work/expeditions.py†L60-L213】【F:great_work/models.py†L122-L206】【F:great_work/data/sideways_effects.yaml†L1-L214】【F:great_work/service.py†L4734-L4999】
- **Gap:** Landmark preparation still collapses into a single block of text and the sideways effect catalogue, while broader, lacks mechanical variety (e.g., faction/tag consequences) tied to the new vignette tags; extend prep copy and hook vignette metadata into faction, theory, or mentorship follow-ons to meet the design’s "adjacent unlock" expectations.【F:docs/HLD.md†L90-L138】【F:great_work/expeditions.py†L120-L320】【F:great_work/data/sideways_vignettes.yaml†L1-L180】

### 3.1 Great Projects - Status

- **Design intent:** Full implementation of Great Projects as large science efforts that unlock new research domains.【F:docs/HLD.md†L61】
- **Implementation status:** Great Projects are selectable via Discord, carry bespoke costs and rewards, and resolve through the shared expedition pipeline.【F:great_work/service.py†L170-L214】【F:great_work/discord_bot.py†L141-L209】【F:great_work/data/settings.yaml†L18-L28】
- **Gap:** None – feature matches the high-level design.

## 4. Influence Economy and Faction Mechanics

- **Design intent:** Influence should operate as a five-dimensional economy with soft caps tied to reputation and faction requirements across key actions, supported by additional sinks such as symposium commitments and contracts.【F:docs/HLD.md†L90-L213】
- **Implementation status:** Influence is stored per faction, clamps to reputation-derived caps, and is spent/earned by expeditions, recruitment, poach/counter offers, symposium pledges, contract upkeep, seasonal commitments, faction projects, and the new `/invest` and `/endow_archive` sinks; `/status` now lists ongoing costs, commitments, investments, and endowments for quick review.【F:great_work/state.py†L18-L2440】【F:great_work/service.py†L677-L4490】【F:great_work/discord_bot.py†L883-L1607】
- **Gap:** With long-tail sinks online, focus shifts to tuning telemetry/alerts and late-game scarcity so high-influence players continue making strategic trade-offs before 1.0.【F:great_work/telemetry.py†L72-L890】【F:docs/implementation_plan.md†L168-L184】

## 5. Press Artefacts and Public Record

- **Design intent:** Every move should produce persona-driven press artefacts that persist in a public archive—bulletins, manifestos, discoveries, retractions, gossip, recruitment notes, defection wires—and stay publicly accessible.【F:docs/HLD.md†L86-L354】
- **Implementation status:** Core actions call structured template generators, archive releases in SQLite, and `/gazette`, `/export_log`, and `/export_web_archive` surface history. Expedition, defection, symposium, mentorship, recruitment, table-talk, sidecast, and admin flows now queue delayed follow-ups via `MultiPressGenerator`, with staggered fast/long cadences delivering gossip, faction briefings, commons roundups, mentorship bulletins, sidecast spotlights, defection epilogues, and administrative updates alongside the primary artefact; tone packs support rotating headlines/blurbs per setting, YAML libraries drive recruitment/table-talk/sidecast copy, deep-prep sideways vignettes now dispatch layered press, and digest ticks mint highlight blurbs from the scheduled press queue.【F:great_work/service.py†L170-L392】【F:great_work/service.py†L680-L744】【F:great_work/service.py†L1013-L1106】【F:great_work/service.py†L1996-L2470】【F:great_work/multi_press.py†L620-L960】【F:great_work/data/recruitment_press.yaml†L1-L48】【F:great_work/data/table_talk_press.yaml†L1-L24】【F:great_work/data/sidecast_arcs.yaml†L1-L60】【F:great_work/data/defection_epilogues.yaml†L1-L32】【F:great_work/data/sideways_vignettes.yaml†L1-L36】【F:great_work/press_tone.py†L1-L102】【F:great_work/state.py†L1-L520】【F:great_work/discord_bot.py†L562-L940】【F:great_work/web_archive.py†L416-L520】
- **Gap:** The new YAML libraries and writing guide broaden coverage, yet we still lack automated tone/safety guardrails (secondary LLM or moderation review) and an explicit process to validate new packs before deployment; the new sidecar plan (`docs/SAFETY_PLAN.md`) captures the Guardian moderation architecture, but implementation remains outstanding.【F:great_work/llm_client.py†L40-L180】【F:docs/WRITING_GUIDE.md†L1-L120】【F:docs/internal/PHASE3_POLISH_DESIGN.md†L80-L110】【F:docs/SAFETY_PLAN.md†L1-L140】

### 5.1 Public archive availability

- **Design intent:** Keep a permanent, public, citable archive beyond Discord.【F:docs/HLD.md†L214-L354】
- **Implementation status:** `/export_web_archive` builds a static site with permalinks, search, and scholar profiles on disk, `/archive_link` retrieves specific headlines, each digest exports the archive automatically, syncs it into the container-served static host, and posts a timestamped ZIP snapshot to the admin channel with retention pruning.【F:great_work/discord_bot.py†L591-L737】【F:great_work/service.py†L1747-L1880】【F:great_work/scheduler.py†L20-L180】【F:docs/internal/ARCHIVE_OPERATIONS.md†L1-L130】
- **Status:** GitHub Pages is now the chosen external host. The scheduler mirrors digest exports into the configured Pages repository, drops `.nojekyll`, and raises telemetry/admin alerts on failure while the nginx container continues to serve the local archive.【F:docs/HLD.md†L214-L354】【F:great_work/scheduler.py†L20-L220】

## 6. Timing, Gazette Cadence, and Symposiums

- **Design intent:** Twice-daily Gazette digests should advance cooldowns, timeline years, and queued orders before publishing to Discord, while weekly symposiums run structured topics with mandatory responses.【F:docs/HLD.md†L101-L386】
- **Implementation status:** `GazetteScheduler` advances the digest, resolves follow-ups/mentorships/conferences, exports the archive, posts to configured channels, emits digest highlight blurbs drawn from the scheduled press queue, raises alerts on slow or thin digests, and sends "upcoming highlights" to an opt-in channel. Weekly symposia now auto-expire stale proposals, enforce per-player backlog caps, score pending topics for freshness/diversity, create pledge rows for every player, settle outstanding symposium debt before new pledges, trigger faction reprisals on sustained debt, and expose per-proposal scoring breakdowns (age decay, fresh bonus, repeat penalty) plus reprisal schedules via `/symposium_backlog` and `/symposium_status`, with telemetry mirroring the same detail for ops review.【F:great_work/scheduler.py†L20-L200】【F:great_work/service.py†L2094-L2700】【F:great_work/service.py†L3450-L3590】【F:great_work/discord_bot.py†L789-L1023】
- **Gap:** Heuristics still need calibration (age weights, bonus/penalty values) and configurable guardrails before release; use the new telemetry to tune thresholds, evaluate fairness for backlog saturation, and document recommended reprisal settings for different player counts.【F:great_work/telemetry.py†L788-L890】【F:docs/internal/PHASE3_POLISH_DESIGN.md†L1-L120】

### 6.1 Non-expedition order batching

- **Design intent:** Orders like mentorships, conferences, and other delayed actions should share a generic batching framework handled at digest time.【F:docs/HLD.md†L101-L213】
- **Implementation status:** A shared `orders` table now feeds dispatcher helpers that activate mentorships, resolve conferences, send symposium reminders, and handle all narrative follow-ups after auto-migrating any legacy rows from the `followups` table.【F:great_work/state.py†L344-L720】【F:great_work/service.py†L1996-L4360】
- **Gap:** Provide moderator tooling to browse and cancel dispatcher orders (beyond the telemetry report) so operators can intervene manually when arcs stall.【F:great_work/state.py†L600-L720】【F:docs/internal/PHASE3_POLISH_DESIGN.md†L1-L120】

## 7. Data Model and Persistence

- **Design intent:** Persist players, scholars, relationships, theories, expeditions, offers, press artefacts, and events with exports available through a bot command.【F:docs/HLD.md†L203-L385】
- **Implementation status:** SQLite schema covers all major entities including offers, mentorships, conferences, symposium topics/votes, and press; the new `orders` table centralises delayed work (mentorship activations, conference resolutions) consumed by the dispatcher, while exports flow through `/export_log` and archive tooling.【F:great_work/state.py†L18-L520】【F:great_work/service.py†L1402-L1880】【F:great_work/discord_bot.py†L562-L737】
- **Gap:** `/gw_admin list_orders` and `/gw_admin cancel_order` now expose dispatcher state, but operators still need exportable order snapshots (CSV/JSON) and migration audit helpers to validate bulk changes safely.【F:great_work/service.py†L3888-L3974】【F:great_work/discord_bot.py†L1405-L1475】

## 8. Discord Command Surface and Admin Tools

- **Design intent:** Provide slash commands for theories, wagers, recruitment, expeditions, conferences, status checks, log exports, and admin hotfixes, with telemetry on usage.【F:docs/HLD.md†L248-L386】
- **Implementation status:** Commands cover the expected surface, including `/poach`, `/counter`, `/view_offers`, `/mentor`, `/assign_lab`, `/conference`, `/export_web_archive`, `/telemetry_report`, and `/gw_admin` subcommands for moderation. All commands now share the telemetry decorator, emitting player, channel, success metrics, layered-press counts, and digest health; operators can review stats via Discord or the bundled telemetry dashboard container.【F:great_work/discord_bot.py†L123-L940】【F:great_work/telemetry_decorator.py†L12-L80】【F:great_work/telemetry.py†L72-L660】【F:ops/telemetry-dashboard/app.py†L1-L64】
- **Gap:** Utility commands such as `/table_talk_summary` and theory lookups still reply ephemerally; convert those outputs into channel posts or pinned references, and extend the new dispatcher consoles with filtering/search so moderators can triage large backlogs quickly.【F:great_work/discord_bot.py†L523-L1475】

### 8.1 Credentials and application configuration

- **Design intent:** Document the runtime configuration (token, app id, channel routing) required to deploy the bot.【F:docs/HLD.md†L248-L286】
- **Implementation status:** The bot reads environment variables for IDs and channel routing, but the design docs still omit a deployment appendix describing the expected configuration.【F:great_work/discord_bot.py†L69-L113】
- **Gap:** Add a short configuration section to docs so operators understand required environment variables and channel mapping.

## 9. LLM and Narrative Integration

- **Design intent:** Generate press and reactions through persona-driven LLM prompts with batching and safety controls.【F:docs/HLD.md†L318-L369】
- **Implementation status:** The LLM client now drives expeditions, defection negotiations, symposium updates, mentorship beats, theory submissions, table-talk posts, and admin notices with persona metadata, retry scheduling, and blocklist safeguards; layered press metrics feed telemetry and tests run in mock mode to verify prompts and pause behaviour.【F:great_work/service.py†L300-L1080】【F:great_work/service.py†L553-L704】【F:great_work/service.py†L631-L704】【F:great_work/llm_client.py†L1-L240】【F:tests/test_game_service.py†L80-L196】【F:tests/test_symposium.py†L20-L69】
- **Gap:** The moderation layer is still limited to a static word list, there's no secondary guard-LLM or redaction workflow, and deeper operator guidance for pause/resume escalation still lives in internal notes pending publication.【F:great_work/llm_client.py†L40-L140】【F:docs/HLD.md†L318-L369】

## Summary of Major Gaps

1. Seasonal commitments, faction projects, faction investments, and archive endowments now anchor long-tail pressure; next quantify balance via telemetry (alert thresholds, dashboards) and decide how relationship deltas unlock additional late-game content.
2. Validate new faction investment/endowment knobs against live telemetry so late-game influence pressure stays meaningful without overwhelming players; fold findings into the economy playbook.
3. Symposium scoring now surfaces weighting math and reprisal cadence; keep tuning heuristics with the new telemetry guardrails and iterate on the published runbook as playtests surface edge cases.【F:docs/TELEMETRY_RUNBOOK.md†L1-L120】
4. Telemetry guardrails now emit webhook alerts and the dashboard exposes dispatcher filters + CSV export; remaining follow-up is product-facing KPIs and tying alerts into broader ops tooling before pilots.
5. Static archives now auto-export, mirror into GitHub Pages, prune old snapshots, and alert operators when disk usage crosses the configured threshold.
