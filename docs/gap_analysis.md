# Gap Analysis: High-Level Design vs. Current Implementation

Last Updated: 2025-09-19 (Post-integration review)

## 1. Scholar Lifecycle and Memory

- **Design intent:** Maintain a roster of 20–30 memorable scholars blending handcrafted legends with procedurally generated additions, spawn sidecast scholars from expeditions, nurture mentorship-driven career growth, and track defections with scars and public fallout.【F:docs/HLD.md†L24-L177】
- **Implementation status:** `GameService` enforces the roster window, seeds new procedurally generated scholars, activates mentorships, progresses mentored careers, and resolves multi-stage defection negotiations via follow-up processing.【F:great_work/service.py†L89-L110】【F:great_work/service.py†L1024-L1105】【F:great_work/service.py†L1832-L1995】【F:great_work/service.py†L572-L760】
- **Gap:** Sidecasts still land as a single gossip artefact with no follow-on scenes, and mentorship/defection events do not yet trigger layered Gazette coverage or persistent scars in the archive beyond a single release.【F:great_work/service.py†L2254-L2287】【F:great_work/press.py†L20-L145】

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
- **Implementation status:** Core actions call structured template generators, archive releases in SQLite, and `/gazette`, `/export_log`, and `/export_web_archive` surface history. A static archive generator produces HTML with search, timelines, and scholar pages.【F:great_work/service.py†L125-L513】【F:great_work/press.py†L20-L145】【F:great_work/discord_bot.py†L562-L637】【F:great_work/web_archive.py†L416-L520】
- **Gap:** The multi-layer press system (`MultiPressGenerator`) is never invoked by the service layer, so most actions emit a single template release and never queue staggered manifestos/gossip. Likewise, the LLM client is unused outside tests, so persona voice and moderation safeguards remain theoretical.【F:great_work/service.py†L170-L392】【F:great_work/multi_press.py†L1-L497】【F:tests/test_multi_press.py†L1-L344】【F:great_work/llm_client.py†L1-L283】

### 5.1 Public archive availability

- **Design intent:** Keep a permanent, public, citable archive beyond Discord.【F:docs/HLD.md†L214-L354】
- **Implementation status:** `/export_web_archive` builds a static site with permalinks, search, and scholar profiles on disk, and `/archive_link` lets users retrieve URLs for specific headlines.【F:great_work/discord_bot.py†L591-L665】【F:great_work/service.py†L1747-L1777】【F:great_work/web_archive.py†L416-L520】
- **Gap:** Hosting/distribution is manual; there is no automated publish step to push the archive to a shared endpoint, so permanency still depends on out-of-band sharing.【F:docs/HLD.md†L214-L354】

## 6. Timing, Gazette Cadence, and Symposiums

- **Design intent:** Twice-daily Gazette digests should advance cooldowns, timeline years, and queued orders before publishing to Discord, while weekly symposiums run structured topics with mandatory responses.【F:docs/HLD.md†L101-L386】
- **Implementation status:** `GazetteScheduler` advances the digest, resolves follow-ups/mentorships/conferences, exports the archive, and posts to configured channels; weekly symposia launch automatically and accept votes via `/symposium_vote`.【F:great_work/scheduler.py†L20-L95】【F:great_work/service.py†L1700-L2059】【F:great_work/discord_bot.py†L503-L543】
- **Gap:** Symposium topics still come from a static random list rather than the player-driven proposal cycle described in the design, and digest summaries do not highlight queued opportunities beyond raw press dumps.【F:docs/HLD.md†L180-L280】【F:great_work/scheduler.py†L52-L86】

### 6.1 Non-expedition order batching

- **Design intent:** Orders like mentorships, conferences, and other delayed actions should share a generic batching framework handled at digest time.【F:docs/HLD.md†L101-L213】
- **Implementation status:** Mentorships and conferences each use bespoke tables and resolver paths inside `_resolve_mentorships()` and `resolve_conferences()`, while follow-ups remain a separate queue.【F:great_work/service.py†L1208-L1386】【F:great_work/service.py†L1934-L2059】
- **Gap:** There is still no unified `orders` table or generic queue/dispatcher, making it hard to add new order types (e.g., symposium commitments) without more bespoke plumbing.【F:great_work/state.py†L18-L141】

## 7. Data Model and Persistence

- **Design intent:** Persist players, scholars, relationships, theories, expeditions, offers, press artefacts, and events with exports available through a bot command.【F:docs/HLD.md†L203-L385】
- **Implementation status:** SQLite schema covers all major entities including offers, mentorships, conferences, symposium topics/votes, and press; exports flow through `/export_log` and the archive tooling.【F:great_work/state.py†L18-L170】【F:great_work/state.py†L636-L944】【F:great_work/discord_bot.py†L562-L637】
- **Gap:** New tables rely on full scans; there are no indexes supporting common lookups (status/date on mentorships, conferences, symposium votes), and no migrations bundle the schema changes, raising operational risk for future deployments.【F:great_work/state.py†L18-L141】

## 8. Discord Command Surface and Admin Tools

- **Design intent:** Provide slash commands for theories, wagers, recruitment, expeditions, conferences, status checks, log exports, and admin hotfixes, with telemetry on usage.【F:docs/HLD.md†L248-L386】
- **Implementation status:** Commands cover the expected surface, including `/poach`, `/counter`, `/view_offers`, `/mentor`, `/assign_lab`, `/conference`, `/export_web_archive`, `/telemetry_report`, and `/gw_admin` subcommands for moderation.【F:great_work/discord_bot.py†L123-L872】
- **Gap:** Telemetry instrumentation is incomplete—only a handful of commands carry the `@track_command` decorator, the decorator silently fails when instantiating `GameService()` without parameters, and several game actions reply ephemerally instead of posting public artefacts.【F:great_work/discord_bot.py†L123-L669】【F:great_work/telemetry_decorator.py†L12-L62】

### 8.1 Credentials and application configuration

- **Design intent:** Document the runtime configuration (token, app id, channel routing) required to deploy the bot.【F:docs/HLD.md†L248-L286】
- **Implementation status:** The bot reads environment variables for IDs and channel routing, but the design docs still omit a deployment appendix describing the expected configuration.【F:great_work/discord_bot.py†L69-L113】
- **Gap:** Add a short configuration section to docs so operators understand required environment variables and channel mapping.

## 9. LLM and Narrative Integration

- **Design intent:** Generate press and reactions through persona-driven LLM prompts with batching and safety controls.【F:docs/HLD.md†L318-L369】
- **Implementation status:** An `LLMClient` module exists with persona prompting, retries, and a basic moderator scaffold, and it is exercised by unit tests.【F:great_work/llm_client.py†L1-L283】【F:tests/test_llm_client.py†L1-L194】
- **Gap:** The LLM client is not wired into the service layer, so production press still relies solely on static templates with no persona voice, moderation, or batching; moderator blocklists remain empty placeholders.【F:great_work/service.py†L170-L513】【F:great_work/llm_client.py†L48-L115】

## Summary of Major Gaps

1. Multi-layer press and persona voice are defined in helpers but never invoked; the Gazette still emits single-template copy without LLM moderation or layered coverage.
2. Influence sinks remain limited to expeditions and poaching, leaving symposium commitments and longer-term obligations unimplemented.
3. Symposium topics and digest summaries are still scheduler-driven placeholders rather than the participatory flows described in the design.
4. Telemetry coverage and configuration documentation lag behind—the decorator fails to capture many commands, and operators lack clear setup guidance.
5. Static archive export exists, but there is no automated publishing pipeline to deliver the archive to players.
