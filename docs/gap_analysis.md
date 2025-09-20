# Gap Analysis: High-Level Design vs. Current Implementation

Last Updated: 2025-09-20 (Phase 3 telemetry & dispatcher audit)

## 1. Scholar Lifecycle and Memory

- **Design intent:** Maintain a roster of 20–30 memorable scholars blending handcrafted legends with procedurally generated additions, spawn sidecast scholars from expeditions, nurture mentorship-driven career growth, and track defections with scars and public fallout.【F:docs/HLD.md†L24-L177】
- **Implementation status:** `GameService` enforces the roster window, seeds new procedurally generated scholars, activates mentorships, progresses mentored careers, and resolves multi-stage defection negotiations with multi-layer press and persona metadata archived alongside outcomes.【F:great_work/service.py†L89-L760】【F:great_work/service.py†L1024-L1995】
- **Gap:** Sidecasts still land as a single gossip artefact with no follow-on scenes, and mentorship arcs have not yet gained layered Gazette coverage or persistent scars beyond their initial announcement.【F:great_work/service.py†L2254-L2287】【F:great_work/press.py†L20-L145】

## 2. Confidence Wagers, Reputation, and Recruitment Effects

- **Design intent:** Confidence wagers must follow the tuned reward/penalty table, clamp reputation within bounds, and impose recruitment cooldowns on high-stakes wagers while recruitment odds reflect cooldowns, faction influence, and unlock thresholds.【F:docs/HLD.md†L44-L138】
- **Implementation status:** Theory and expedition commands require explicit confidence levels; resolutions apply wager tables, clamp reputation, enforce cooldowns, and recruitment odds include influence bonuses plus cooldown penalties, all surfaced through `/status` and `/wager`.【F:great_work/service.py†L125-L318】【F:great_work/service.py†L320-L418】【F:great_work/discord_bot.py†L123-L210】【F:great_work/discord_bot.py†L523-L571】
- **Gap:** Recruitment odds are calculated server-side but not exposed ahead of confirmation, leaving players without the comparative odds table promised in the UX guidelines.【F:docs/HLD.md†L100-L138】【F:great_work/discord_bot.py†L209-L247】

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
- **Implementation status:** Influence is stored per faction, clamps to reputation-derived caps, and is spent/earned by expeditions, recruitment, and poach/counter offers with escrow and sideways effects adjusting totals. `/status` exposes the caps and thresholds.【F:great_work/state.py†L18-L170】【F:great_work/service.py†L677-L835】【F:great_work/service.py†L520-L760】【F:great_work/discord_bot.py†L523-L600】
- **Gap:** Symposium participation and long-term contract upkeep still cost nothing, so the broader economy lacks the sustained sinks highlighted in the design (e.g., symposium pledges, seasonal commitments).【F:docs/HLD.md†L126-L213】【F:great_work/service.py†L1295-L1448】

## 5. Press Artefacts and Public Record

- **Design intent:** Every move should produce persona-driven press artefacts that persist in a public archive—bulletins, manifestos, discoveries, retractions, gossip, recruitment notes, defection wires—and stay publicly accessible.【F:docs/HLD.md†L86-L354】
- **Implementation status:** Core actions call structured template generators, archive releases in SQLite, and `/gazette`, `/export_log`, and `/export_web_archive` surface history. Expedition, defection, and symposium flows now queue delayed follow-ups via `MultiPressGenerator`, with scheduled gossip and faction statements releasing over time alongside the primary artefact.【F:great_work/service.py†L170-L1850】【F:great_work/multi_press.py†L1-L520】【F:great_work/state.py†L1-L220】【F:great_work/discord_bot.py†L562-L737】【F:great_work/web_archive.py†L416-L520】
- **Gap:** Mentorship/admin maintenance events still emit single-template copy, and staged drops are not yet summarised in Gazette digests or surfaced via operator dashboards.【F:great_work/service.py†L1200-L2060】【F:great_work/multi_press.py†L1-L520】

### 5.1 Public archive availability

- **Design intent:** Keep a permanent, public, citable archive beyond Discord.【F:docs/HLD.md†L214-L354】
- **Implementation status:** `/export_web_archive` builds a static site with permalinks, search, and scholar profiles on disk, `/archive_link` retrieves specific headlines, and each digest now exports the archive automatically and posts a timestamped ZIP snapshot to the admin channel.【F:great_work/discord_bot.py†L591-L737】【F:great_work/service.py†L1747-L1880】【F:great_work/scheduler.py†L20-L120】【F:docs/internal/ARCHIVE_OPERATIONS.md†L1-L120】
- **Gap:** Hosting to a public endpoint still requires manual intervention or bespoke scripts; we also need rotation tooling for snapshots shipped to Discord to avoid unbounded storage growth.【F:docs/HLD.md†L214-L354】【F:great_work/scheduler.py†L20-L120】

## 6. Timing, Gazette Cadence, and Symposiums

- **Design intent:** Twice-daily Gazette digests should advance cooldowns, timeline years, and queued orders before publishing to Discord, while weekly symposiums run structured topics with mandatory responses.【F:docs/HLD.md†L101-L386】
- **Implementation status:** `GazetteScheduler` advances the digest, resolves follow-ups/mentorships/conferences, exports the archive, and posts to configured channels; weekly symposia launch automatically and accept votes via `/symposium_vote`.【F:great_work/scheduler.py†L20-L95】【F:great_work/service.py†L1700-L2059】【F:great_work/discord_bot.py†L503-L543】
- **Gap:** Symposium topics still come from a static random list rather than the player-driven proposal cycle described in the design, and digest summaries do not highlight queued opportunities beyond raw press dumps.【F:docs/HLD.md†L180-L280】【F:great_work/scheduler.py†L52-L86】

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
- **Implementation status:** Commands cover the expected surface, including `/poach`, `/counter`, `/view_offers`, `/mentor`, `/assign_lab`, `/conference`, `/export_web_archive`, `/telemetry_report`, and `/gw_admin` subcommands for moderation. All commands now share the telemetry decorator, emitting player, channel, and success metrics alongside LLM latency and pause events.【F:great_work/discord_bot.py†L123-L950】【F:great_work/telemetry_decorator.py†L12-L67】【F:great_work/telemetry.py†L72-L520】
- **Gap:** Engagement dashboards and layered press counts are still missing from `/telemetry_report`, and several actions continue to answer ephemerally instead of posting public artefacts, keeping the "all moves are public" requirement partially met.【F:great_work/discord_bot.py†L597-L772】【F:great_work/telemetry.py†L337-L520】

### 8.1 Credentials and application configuration

- **Design intent:** Document the runtime configuration (token, app id, channel routing) required to deploy the bot.【F:docs/HLD.md†L248-L286】
- **Implementation status:** The bot reads environment variables for IDs and channel routing, but the design docs still omit a deployment appendix describing the expected configuration.【F:great_work/discord_bot.py†L69-L113】
- **Gap:** Add a short configuration section to docs so operators understand required environment variables and channel mapping.

## 9. LLM and Narrative Integration

- **Design intent:** Generate press and reactions through persona-driven LLM prompts with batching and safety controls.【F:docs/HLD.md†L318-L369】
- **Implementation status:** The LLM client now drives expeditions, defection negotiations, symposium updates, and admin notices with persona metadata and blocklist safeguards. Tests run in mock mode to verify prompts and pause behaviour.【F:great_work/service.py†L300-L1040】【F:tests/test_game_service.py†L80-L196】【F:tests/test_symposium.py†L20-L69】
- **Gap:** Digest/scheduler loops still publish immediately without staged delays, and persona voice remains static for table-talk/utility commands. Pause/resume depends on manual admin intervention until telemetry-driven automation is added.【F:great_work/service.py†L90-L230】【F:great_work/scheduler.py†L24-L116】

## Summary of Major Gaps

1. Multi-layer press now stages expedition/defection/symposium follow-ups, yet mentorship/admin events lack layered coverage and Gazette summaries do not highlight queued drops.
2. Influence sinks remain limited to expeditions and poaching, leaving symposium commitments and longer-term obligations unimplemented.
3. Symposium topics and digest summaries are still scheduler-driven placeholders rather than the participatory flows described in the design.
4. Telemetry dashboards and deployment guidance lag behind—commands emit LLM/channel metrics, yet layered-press counts, success criteria, and operator setup docs remain outstanding.
5. Static archives now auto-export and post ZIP snapshots to the admin channel after each digest, yet automated publishing to a public host and snapshot rotation tooling are still open.
