# Gap Analysis: High-Level Design vs. Current Implementation

## 1. Scholar Lifecycle and Memory
- **Design intent:** Maintain a roster of 20–30 memorable scholars that mix hand-authored legends with procedurally generated characters, spawn sidecast scholars from expeditions, nurture mentorship growth, and track defections with persistent scars and public fallout.【F:docs/HLD.md†L26-L201】
- **Implementation status:** `GameService` enforces a minimum roster, seeds procedurally generated scholars, spawns sidecasts on successful expeditions, records relationship changes, and publishes defection outcomes while applying memory scars.【F:great_work/service.py†L60-L551】 Persistence layers store scholar data, relationships, press releases, and events to back these flows.【F:great_work/state.py†L22-L233】
- **Gap:** The roster is only back-filled upward—there is no retirement logic, mentorship advancement, or career progression to keep the pool curated within the 20–30 window, and sidecasts do not yet branch into longer arcs beyond their initial gossip beat.【F:docs/HLD.md†L165-L213】【F:great_work/service.py†L463-L551】

## 2. Confidence Wagers, Reputation, and Recruitment Effects
- **Design intent:** Confidence wagers should respect the tuned reward/penalty table, clamp reputation within bounds, and impose a two-tick recruitment cooldown after staking one’s career; recruitment odds should respond to cooldowns and influence while action unlocks respect reputation thresholds.【F:docs/HLD.md†L44-L116】
- **Implementation status:** Reputation adjustments use the configured wager table, apply bounds, and set a recruitment cooldown that halves success chances until `advance_digest` decays it; recruitment attempts modify scholar feelings, influence, and emit press.【F:great_work/service.py†L228-L368】【F:great_work/models.py†L86-L117】
- **Gap:** Reputation is not yet consulted to gate actions, cooldown decay relies on manual digest advancement, and recruitment remains inaccessible through the Discord surface, limiting the intended gameplay impact.【F:docs/HLD.md†L54-L116】【F:great_work/service.py†L304-L437】【F:great_work/discord_bot.py†L14-L110】

## 3. Expedition Structure and Outcomes
- **Design intent:** Distinct expedition types with tailored prep modifiers, influence costs, and prep-depth-dependent failure tables should surface sideways discoveries, gossip, and faction fallout.【F:docs/HLD.md†L57-L138】
- **Implementation status:** Launching an expedition records the declared type, applies faction costs and rewards, resolves outcomes via the shared resolver, updates relationships, and may spawn a sidecast gossip item on non-failures.【F:great_work/service.py†L158-L551】【F:great_work/expeditions.py†L1-L74】【F:great_work/press.py†L14-L107】
- **Gap:** Resolution still treats all types identically aside from influence math, sideways discoveries use static text, and there are no differentiated prep tracks, failure-table flavour, or faction gossip hooks after spectacular failures.【F:docs/HLD.md†L77-L138】【F:great_work/expeditions.py†L57-L74】

## 4. Influence Economy and Faction Mechanics
- **Design intent:** Influence is a five-vector economy with soft caps tied to reputation and faction requirements on key actions.【F:docs/HLD.md†L65-L138】
- **Implementation status:** Influence is stored per player, expeditions charge and reward faction influence, and recruitment success can grant faction points.【F:great_work/models.py†L86-L117】【F:great_work/service.py†L158-L368】
- **Gap:** Soft caps, faction gating for orders, and broader influence sinks/sources (e.g., symposiums or contracts) remain absent, leaving the economy unbalanced.【F:docs/HLD.md†L90-L138】【F:great_work/service.py†L490-L505】

## 5. Press Artefacts and Public Record
- **Design intent:** All moves should yield rich, persona-driven press artefacts that persist in a public archive, spanning bulletins, manifestos, discoveries, retractions, gossip, recruitment notes, and defection wires.【F:docs/HLD.md†L86-L266】【F:docs/HLD.md†L318-L354】
- **Implementation status:** Templates cover each press type, and the service archives every generated release (including recruitment and defection) into a dedicated database table alongside event logs.【F:great_work/press.py†L14-L122】【F:great_work/service.py†L113-L368】【F:great_work/state.py†L22-L233】
- **Gap:** Text remains purely templated without persona/LLM styling, gossip triggers only cover sidecasts and recruitment, and there is no surfaced public archive or Discord publishing pipeline yet.【F:docs/HLD.md†L214-L266】【F:great_work/service.py†L297-L355】【F:great_work/discord_bot.py†L14-L110】

## 6. Timing, Gazette Cadence, and Symposiums
- **Design intent:** Twice-daily Gazette digests should process all queued orders, advance cooldown ticks, and publish to Discord, while weekly symposiums drive mandatory public stances.【F:docs/HLD.md†L101-L280】【F:docs/HLD.md†L381-L386】
- **Implementation status:** The background scheduler runs digest jobs that resolve expeditions and logs a symposium heartbeat, but digest advancement does not tick cooldowns or publish summaries beyond server logs.【F:great_work/scheduler.py†L1-L43】【F:great_work/service.py†L228-L437】
- **Gap:** Need to integrate digest advancement (`advance_digest`), broaden the queued order system, and push Gazette/symposium artefacts to Discord with the promised participation mechanics.【F:docs/HLD.md†L101-L280】【F:great_work/discord_bot.py†L14-L110】

## 7. Data Model and Persistence
- **Design intent:** Persist players, scholars, relationships, theories, expeditions, offers, press artefacts, and events, exposing them through an `/export_log` command.【F:docs/HLD.md†L203-L346】【F:docs/HLD.md†L384-L385】
- **Implementation status:** The SQLite schema already covers players, scholars, events, theories, expeditions, press releases, relationships, and offers, with helpers to record and retrieve each artefact.【F:great_work/state.py†L22-L233】
- **Gap:** There is still no surfaced export endpoint, no persistence for faction standings beyond influence totals, and no tooling around offers/contracts to realise the documented workflows.【F:docs/HLD.md†L203-L346】【F:great_work/state.py†L71-L233】

## 8. Discord Command Surface and Admin Tools
- **Design intent:** Offer slash commands for theories, wagers, recruitment, expeditions, conferences, status checks, log export, and at least one admin hotfix entry point.【F:docs/HLD.md†L248-L386】
- **Implementation status:** The bot exposes only `/submit_theory`, `/launch_expedition`, and `/resolve_expeditions`, with no recruitment, status, export, or admin commands wired up.【F:great_work/discord_bot.py†L14-L110】
- **Gap:** Expand the command surface to include the documented gameplay and admin flows, wiring them into the new recruitment/defection services and export tooling.【F:docs/HLD.md†L248-L386】【F:great_work/service.py†L304-L428】

## 9. LLM and Narrative Integration
- **Design intent:** Generate press and scholar reactions through persona-driven LLM prompts with batching and moderation safeguards.【F:docs/HLD.md†L318-L369】
- **Implementation status:** Scholar reactions and press copy remain templated string substitutions without any LLM calls or safety layers.【F:great_work/service.py†L553-L569】【F:great_work/press.py†L14-L122】
- **Gap:** Introduce the planned persona prompt pipeline, batching strategies, and moderation checks to reach the intended narrative richness.【F:docs/HLD.md†L318-L369】

## Remediation Progress Snapshot
- **Gazette delivery:** The scheduler now accepts an optional publisher so digest and symposium artefacts can be routed directly to Discord or other channels instead of relying solely on logs.【F:great_work/scheduler.py†L15-L64】
- **Public archive access:** Players can browse recent Gazette headlines through the `/gazette` slash command, which surfaces stored press releases via the `GameService` archive helpers.【F:great_work/discord_bot.py†L118-L156】【F:great_work/service.py†L473-L501】
