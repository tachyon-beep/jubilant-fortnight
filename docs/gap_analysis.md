# Gap Analysis: High-Level Design vs. Current Implementation

## 1. Scholar Lifecycle and Memory
- **Design intent:** Maintain a roster of 20–30 memorable scholars that mix hand-authored legends with procedurally generated characters, spawn sidecast scholars from expeditions, nurture mentorship growth, and track defections with persistent scars and public fallout.【F:docs/HLD.md†L26-L213】
- **Implementation status:** `GameService` seeds the roster on boot, keeps headcount between 20 and 30 by generating new scholars or retiring low-attachment figures, and archives the related events through `GameState`. Digest advancement advances careers and resolves scheduled follow-ups, emitting gossip press and saving the results in SQLite.【F:great_work/service.py†L86-L168】【F:great_work/service.py†L494-L666】【F:great_work/state.py†L200-L305】
- **Gap:** Mentorship actions and long-form career management remain absent, sidecasts end after a single gossip item, and follow-up resolutions only adjust feelings without triggering return offers or multi-step defection arcs.【F:docs/HLD.md†L165-L213】【F:great_work/service.py†L629-L738】

## 2. Confidence Wagers, Reputation, and Recruitment Effects
- **Design intent:** Confidence wagers should respect the tuned reward/penalty table, clamp reputation within bounds, and impose a two-tick recruitment cooldown after staking one’s career; recruitment odds should respond to cooldowns and influence while action unlocks respect reputation thresholds.【F:docs/HLD.md†L44-L138】
- **Implementation status:** Reputation adjustments honour the wager table and configured bounds, expedition and recruitment commands enforce reputation thresholds, recruitment odds reflect cooldowns and faction influence, and the `/status` and `/wager` commands now expose current thresholds, bounds, and stake payouts directly in Discord.【F:great_work/service.py†L170-L392】【F:great_work/service.py†L468-L505】【F:great_work/discord_bot.py†L148-L184】
- **Gap:** Confidence information is surfaced, but forthcoming wager/conference actions still need explicit Discord flows and gating once those mechanics are built.【F:docs/HLD.md†L101-L138】【F:great_work/discord_bot.py†L148-L184】

## 3. Expedition Structure and Outcomes
- **Design intent:** Distinct expedition types with tailored prep modifiers, influence costs, and prep-depth-dependent failure tables should surface sideways discoveries, gossip, and faction fallout.【F:docs/HLD.md†L57-L138】
- **Implementation status:** Expedition launches levy type-specific influence costs, store preparation detail, and resolve through an `ExpeditionResolver` that rolls d100, applies modifiers, and consults depth-aware failure and sideways tables before archiving outcomes and reactions.【F:great_work/service.py†L170-L318】【F:great_work/expeditions.py†L60-L116】【F:great_work/data/failure_tables.yaml†L1-L44】【F:great_work/press.py†L40-L92】
- **Gap:** Sideways discoveries still return flavour text only—there are no faction swings, queued follow-up orders, or differentiated consequences beyond the message templates, and expedition prep depth does not yet branch into bespoke narrative threads.【F:docs/HLD.md†L90-L138】【F:great_work/press.py†L61-L75】

## 4. Influence Economy and Faction Mechanics
- **Design intent:** Influence is a five-vector economy with soft caps tied to reputation and faction requirements on key actions.【F:docs/HLD.md†L90-L138】
- **Implementation status:** Players store faction influence with caps derived from reputation, expeditions deduct and reward influence per faction, recruitment adjusts the chosen faction, and status exports show current totals and caps.【F:great_work/service.py†L170-L392】【F:great_work/service.py†L677-L773】【F:great_work/discord_bot.py†L148-L162】
- **Gap:** Additional sinks and faction-gated activities (symposium commitments, contracts, offers) are still missing, so influence rarely shifts outside expeditions and recruitment and lacks the balancing pressure described in the design.【F:docs/HLD.md†L104-L213】【F:great_work/service.py†L677-L738】

## 5. Press Artefacts and Public Record
- **Design intent:** All moves should yield rich, persona-driven press artefacts that persist in a public archive, spanning bulletins, manifestos, discoveries, retractions, gossip, recruitment notes, and defection wires.【F:docs/HLD.md†L86-L354】
- **Implementation status:** Major actions produce press releases through templated generators, the service archives the results, and Discord commands expose Gazette headlines and exportable logs backed by SQLite persistence.【F:great_work/press.py†L20-L155】【F:great_work/service.py†L125-L392】【F:great_work/state.py†L366-L417】【F:great_work/discord_bot.py†L164-L191】
- **Gap:** Copy remains purely templated with no persona or LLM voice, Gazette digests still rely on optional publishers instead of an automated public archive, and most action types only generate one artefact per move.【F:docs/HLD.md†L214-L354】【F:great_work/scheduler.py†L41-L69】

## 6. Timing, Gazette Cadence, and Symposiums
- **Design intent:** Twice-daily Gazette digests should process all queued orders, advance cooldown ticks, and publish to Discord, while weekly symposiums drive mandatory public stances.【F:docs/HLD.md†L101-L386】
- **Implementation status:** `GazetteScheduler` schedules digests and a weekly symposium heartbeat, calling `advance_digest` to decay cooldowns, advance the timeline, maintain the roster, progress careers, and resolve follow-ups before expedition resolution.【F:great_work/scheduler.py†L30-L58】【F:great_work/service.py†L494-L666】
- **Gap:** Digest output still depends on providing an external publisher (no default Discord wiring), the symposium flow emits only a placeholder heartbeat, and non-expedition orders remain unsupported during the digest cadence.【F:docs/HLD.md†L101-L280】【F:great_work/scheduler.py†L41-L58】

## 7. Data Model and Persistence
- **Design intent:** Persist players, scholars, relationships, theories, expeditions, offers, press artefacts, and events, exposing them through an `/export_log` command.【F:docs/HLD.md†L203-L385】
- **Implementation status:** The SQLite schema stores players, scholars, relationships, events, expeditions, theories, press releases, offers, and follow-ups, and the service exposes both a press archive and `/export_log` command to retrieve stored artefacts.【F:great_work/state.py†L18-L417】【F:great_work/service.py†L486-L506】【F:great_work/discord_bot.py†L164-L191】
- **Gap:** Offer records and contracts are still unused, faction standings beyond influence are absent, and many lifecycle events (e.g., mentorship, symposium results) are not yet persisted because the mechanics themselves are missing.【F:docs/HLD.md†L203-L346】【F:great_work/state.py†L77-L305】

## 8. Discord Command Surface and Admin Tools
- **Design intent:** Offer slash commands for theories, wagers, recruitment, expeditions, conferences, status checks, log export, and at least one admin hotfix entry point.【F:docs/HLD.md†L248-L386】
- **Implementation status:** Discord currently supports theory submission, expedition launch/resolution, recruitment, wager lookups, player status, Gazette browsing, and log export through dedicated slash commands backed by the service layer.【F:great_work/discord_bot.py†L33-L220】
- **Gap:** The `/conference` and admin hotfix flows remain absent, channel-specific publishing is not automated, and defection tooling is still service-only with no Discord triggers.【F:docs/HLD.md†L248-L386】【F:great_work/discord_bot.py†L33-L220】

## 9. LLM and Narrative Integration
- **Design intent:** Generate press and scholar reactions through persona-driven LLM prompts with batching and moderation safeguards.【F:docs/HLD.md†L318-L369】
- **Implementation status:** Scholar reactions and press copy remain templated string substitutions without any LLM calls or safety layers.【F:great_work/press.py†L20-L155】
- **Gap:** Introduce the planned persona prompt pipeline, batching strategies, and moderation checks to reach the intended narrative richness.【F:docs/HLD.md†L318-L369】【F:great_work/press.py†L20-L155】

## Remediation Progress Snapshot
- **Digest cadence:** `advance_digest` now rolls into the scheduled Gazette loop, ensuring cooldown decay, career progression, roster curation, and follow-up gossip fire automatically before expedition resolution.【F:great_work/service.py†L494-L666】【F:great_work/scheduler.py†L41-L48】
- **Discord surface:** The `/recruit`, `/status`, `/wager`, `/gazette`, and `/export_log` commands expose recruitment, economy telemetry, and historical press directly in Discord, reducing the tooling gap for core gameplay loops.【F:great_work/discord_bot.py†L123-L220】【F:great_work/service.py†L320-L505】
