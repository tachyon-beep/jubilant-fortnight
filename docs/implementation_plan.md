# Implementation Plan to Close Documented Gaps

## 1. Scholar Lifecycle and Defection Systems
- Extend persistence with scholar relationship, contract, and career tables plus a sidecast queue so the service can maintain a 20–30 character roster and spawn expedition side discoveries on partial or better results.【F:docs/HLD.md†L26-L200】【F:great_work/state.py†L14-L141】
- Add GameService hooks that evaluate roster size after each digest, trigger procedural generation via `ScholarRepository.generate`, and append Gazette events describing mentorship progress or defections.【F:docs/HLD.md†L171-L201】【F:great_work/service.py†L118-L217】【F:great_work/scholars.py†L87-L184】
- Implement public defection handling that uses the logistic helper, updates memory scars, and emits press plus reputation adjustments tied to scholar integrity.【F:docs/HLD.md†L176-L201】【F:great_work/scholars.py†L162-L184】【F:great_work/press.py†L60-L93】

## 2. Confidence, Reputation, and Recruitment Effects
- Track player reputation within the configured bounds and enforce unlock thresholds for actions; persist cooldown tokens after “stake my career” wagers to gate recruitment odds.【F:docs/HLD.md†L44-L116】【F:great_work/config.py†L14-L58】【F:great_work/service.py†L118-L217】
- Introduce recruitment mechanics that consult cooldown status and influence, reducing success probability when the cooldown is active and publishing appropriate gossip when attempts fail.【F:docs/HLD.md†L54-L116】【F:docs/HLD.md†L86-L138】

## 3. Expedition Typing and Influence Economy
- Differentiate expedition types in the command surface and service layer, applying distinct prep modifiers, influence costs, and unlock conditions per design.【F:docs/HLD.md†L57-L138】【F:great_work/service.py†L118-L190】
- Expand `ExpeditionPreparation` to capture think tank, expertise, site, and political modifiers separately, then consume player influence balances with soft caps that scale from reputation.【F:docs/HLD.md†L117-L138】【F:great_work/models.py†L73-L118】【F:great_work/service.py†L118-L217】
- Enrich failure handling so sideways discoveries feed faction reactions, gossip, and potential new scholar sidecasts using the failure table depth selected during preparation.【F:docs/HLD.md†L77-L138】【F:great_work/expeditions.py†L48-L103】【F:great_work/press.py†L60-L93】

## 4. Press Artefacts and Narrative Delivery
- Persist press releases in their own table linked to events and expose them via `/export_log`, ensuring bulletins, manifestos, discovery reports, retractions, and gossip follow the high-level templates.【F:docs/HLD.md†L86-L266】【F:docs/HLD.md†L384-L385】【F:great_work/state.py†L14-L141】
- Introduce AI-backed or persona-scripted generation for scholar reactions and gossip, adding moderation hooks and batching per the design’s safety notes.【F:docs/HLD.md†L318-L369】【F:great_work/service.py†L202-L216】【F:great_work/press.py†L60-L93】

## 5. Gazette Cadence and Symposium Flow
- Enhance the scheduler to publish digests and symposium recaps directly into Discord channels, including queued orders beyond expeditions and public stances during weekly events.【F:docs/HLD.md†L101-L280】【F:great_work/scheduler.py†L23-L43】【F:great_work/discord_bot.py†L19-L132】
- Model symposium topics and required responses so players must submit positions by the deadline, with reputation or influence consequences for participation or silence.【F:docs/HLD.md†L101-L280】

## 6. Command Surface and Admin Tools
- Implement the remaining slash commands (`/wager`, `/recruit`, `/conference`, `/status`, `/export_log`) and provide at least one admin hotfix command that can adjust state safely.【F:docs/HLD.md†L248-L386】【F:great_work/discord_bot.py†L33-L132】
- Surface player status summaries (reputation, influence, cooldowns, pending orders) through the bot to make the game state transparent in chat.【F:docs/HLD.md†L248-L286】【F:great_work/service.py†L64-L217】

## 7. Data Model and Tooling
- Migrate the SQLite schema to include factions, theories, expeditions, offers, press releases, and relationships, plus views that power the planned status and export commands.【F:docs/HLD.md†L203-L346】【F:great_work/state.py†L14-L141】
- Provide migration scripts/tests covering the expanded schema along with deterministic fixtures so automated tests validate RNG-dependent flows.【F:docs/HLD.md†L323-L359】【F:great_work/rng.py†L1-L41】【F:tests/test_expedition_resolver.py†L1-L120】
