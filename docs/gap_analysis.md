# Gap Analysis: High-Level Design vs. Current Implementation

## 1. Scholar Lifecycle and Memory
- **Design intent:** Maintain a roster of 20–30 memorable scholars that mix hand-authored legends with procedurally generated characters, spawn sidecast scholars from expeditions, nurture mentorship growth, and track defections with persistent scars and public fallout.【F:docs/HLD.md†L26-L213】
- **Implementation status:** `GameService` now caps the roster between 20 and 30, retiring low-attachment scholars, spawning procedurally generated sidecasts, and persisting the resulting events.【F:great_work/service.py†L85-L214】【F:great_work/service.py†L440-L535】 Digest advancement advances careers, emits gossip for promotions, and resolves scheduled follow-ups from recruitment or defection arcs, all of which are archived in SQLite via `GameState`.【F:great_work/service.py†L536-L633】【F:great_work/state.py†L20-L233】
- **Gap:** Mentorship actions and long-form career management remain absent, sidecasts end after a single gossip item, and follow-up resolutions only adjust feelings without triggering return offers or multi-step defection arcs.【F:docs/HLD.md†L165-L213】【F:great_work/service.py†L536-L633】

## 2. Confidence Wagers, Reputation, and Recruitment Effects
- **Design intent:** Confidence wagers should respect the tuned reward/penalty table, clamp reputation within bounds, and impose a two-tick recruitment cooldown after staking one’s career; recruitment odds should respond to cooldowns and influence while action unlocks respect reputation thresholds.【F:docs/HLD.md†L44-L116】
- **Implementation status:** Reputation adjustments honour the wager table and bounds, staking a career applies the documented cooldown penalty, and reputation thresholds gate expedition and recruitment commands exposed through Discord.【F:great_work/service.py†L214-L383】【F:great_work/config.py†L10-L53】【F:great_work/discord_bot.py†L20-L150】 The digest loop now decays cooldowns automatically and the `/status` command surfaces current influence, caps, and cooldown timers.【F:great_work/service.py†L518-L566】【F:great_work/discord_bot.py†L118-L150】
- **Gap:** Players still lack visibility into the exact reputation thresholds and wager table in the Discord UX, and future actions (e.g., conferences or wagers) remain to be gated and surfaced once implemented.【F:docs/HLD.md†L101-L138】【F:great_work/discord_bot.py†L118-L150】

## 3. Expedition Structure and Outcomes
- **Design intent:** Distinct expedition types with tailored prep modifiers, influence costs, and prep-depth-dependent failure tables should surface sideways discoveries, gossip, and faction fallout.【F:docs/HLD.md†L57-L138】
- **Implementation status:** Expedition launches levy type-specific influence costs, store preparation detail, and resolve through a resolver that rolls d100, applies modifiers, and consults failure tables and sideways discovery text per type and depth.【F:great_work/service.py†L214-L383】【F:great_work/expeditions.py†L12-L86】【F:great_work/data/failure_tables.yaml†L1-L44】 Outcomes adjust relationships, award influence, and can spawn sidecast recruits with archived press.【F:great_work/service.py†L383-L506】
- **Gap:** Sideways discoveries still return flavour text only—there are no faction swings, queued follow-up orders, or differentiated consequences beyond the message templates, and expedition prep depth does not yet branch into bespoke narrative threads.【F:docs/HLD.md†L90-L138】【F:great_work/service.py†L383-L506】

## 4. Influence Economy and Faction Mechanics
- **Design intent:** Influence is a five-vector economy with soft caps tied to reputation and faction requirements on key actions.【F:docs/HLD.md†L90-L138】
- **Implementation status:** Players store faction influence with caps computed from reputation, expeditions deduct and reward influence per faction, and recruitment success boosts the chosen faction while status exports show current totals and caps.【F:great_work/service.py†L214-L506】【F:great_work/models.py†L86-L141】【F:great_work/discord_bot.py†L118-L150】
- **Gap:** Additional sinks and faction-gated activities (symposium commitments, contracts, offers) are still missing, so influence rarely shifts outside expeditions and recruitment and lacks the balancing pressure described in the design.【F:docs/HLD.md†L104-L213】【F:great_work/service.py†L506-L633】

## 5. Press Artefacts and Public Record
- **Design intent:** All moves should yield rich, persona-driven press artefacts that persist in a public archive, spanning bulletins, manifestos, discoveries, retractions, gossip, recruitment notes, and defection wires.【F:docs/HLD.md†L86-L266】【F:docs/HLD.md†L318-L354】
- **Implementation status:** Every major action produces a press release through the templated generators, the service archives the results, and Discord commands expose recent Gazette headlines and exportable logs backed by SQLite persistence.【F:great_work/press.py†L12-L128】【F:great_work/service.py†L120-L506】【F:great_work/discord_bot.py†L86-L176】
- **Gap:** Copy remains purely templated with no persona/LLM voice, and Gazette digests are still delivered ad hoc—there is no automated public archive channel or per-action gossip beyond recruitment, follow-ups, and sidecasts.【F:docs/HLD.md†L214-L354】【F:great_work/scheduler.py†L12-L64】

## 6. Timing, Gazette Cadence, and Symposiums
- **Design intent:** Twice-daily Gazette digests should process all queued orders, advance cooldown ticks, and publish to Discord, while weekly symposiums drive mandatory public stances.【F:docs/HLD.md†L101-L280】【F:docs/HLD.md†L381-L386】
- **Implementation status:** `GazetteScheduler` now schedules digests, calls `advance_digest`, and resolves expeditions before emitting releases, while the digest itself triggers cooldown decay, roster maintenance, career promotions, and follow-up gossip.【F:great_work/scheduler.py†L12-L64】【F:great_work/service.py†L506-L633】
- **Gap:** Digest output still relies on optional publishers (no default Discord wiring), there is no symposium content pipeline beyond a placeholder heartbeat, and non-expedition orders remain unsupported during the digest cadence.【F:docs/HLD.md†L101-L280】【F:great_work/scheduler.py†L12-L64】

## 7. Data Model and Persistence
- **Design intent:** Persist players, scholars, relationships, theories, expeditions, offers, press artefacts, and events, exposing them through an `/export_log` command.【F:docs/HLD.md†L203-L346】【F:docs/HLD.md†L384-L385】
- **Implementation status:** The SQLite schema stores players, scholars, relationships, events, expeditions, theories, press releases, offers, and follow-ups, and the service exposes both a press archive and `/export_log` command to retrieve stored artefacts.【F:great_work/state.py†L18-L233】【F:great_work/service.py†L472-L566】【F:great_work/discord_bot.py†L142-L176】
- **Gap:** Offer records and contracts are still unused, faction standings beyond influence are absent, and many lifecycle events (e.g., mentorship, symposium results) are not yet persisted because the mechanics themselves are missing.【F:docs/HLD.md†L203-L346】【F:great_work/state.py†L94-L210】

## 8. Discord Command Surface and Admin Tools
- **Design intent:** Offer slash commands for theories, wagers, recruitment, expeditions, conferences, status checks, log export, and at least one admin hotfix entry point.【F:docs/HLD.md†L248-L386】
- **Implementation status:** Discord currently supports theory submission, expedition launch/resolution, recruitment, player status, Gazette browsing, and log export through dedicated slash commands backed by the service layer.【F:great_work/discord_bot.py†L32-L176】
- **Gap:** The `/wager`, `/conference`, and admin hotfix flows remain absent, channel-specific publishing is not automated, and defection tooling is still service-only with no Discord triggers.【F:docs/HLD.md†L248-L386】【F:great_work/discord_bot.py†L32-L176】

## 9. LLM and Narrative Integration
- **Design intent:** Generate press and scholar reactions through persona-driven LLM prompts with batching and moderation safeguards.【F:docs/HLD.md†L318-L369】
- **Implementation status:** Scholar reactions and press copy remain templated string substitutions without any LLM calls or safety layers.【F:great_work/service.py†L613-L633】【F:great_work/press.py†L12-L128】
- **Gap:** Introduce the planned persona prompt pipeline, batching strategies, and moderation checks to reach the intended narrative richness.【F:docs/HLD.md†L318-L369】

## Remediation Progress Snapshot
- **Digest cadence:** `advance_digest` now rolls into the scheduled Gazette loop, ensuring cooldown decay, career progression, roster curation, and follow-up gossip fire automatically before expedition resolution.【F:great_work/scheduler.py†L34-L53】【F:great_work/service.py†L506-L633】
- **Discord surface:** Newly added `/recruit`, `/status`, `/gazette`, and `/export_log` commands expose recruitment, economy telemetry, and historical press directly in Discord, reducing the tooling gap for core gameplay loops.【F:great_work/discord_bot.py†L86-L176】【F:great_work/service.py†L347-L566】
