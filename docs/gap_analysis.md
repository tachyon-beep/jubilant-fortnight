# Gap Analysis: High-Level Design vs. Current Implementation

## 1. Scholar Lifecycle and Memory
- **Design intent:** Maintain a roster of 20–30 memorable scholars that combine hand-authored legends with procedurally generated characters, including sidecast scholars emerging from expeditions, mentorship growth, and public defections with long-term grudges tracked via facts, feelings, and scars.【F:docs/HLD.md†L26-L200】【F:docs/HLD.md†L171-L201】
- **Implementation status:** The codebase loads static seed scholars and supports deterministic generation plus basic memory serialization, but only seeds once at startup with no ongoing roster management or hooks to expeditions for spawning newcomers.【F:great_work/service.py†L48-L158】【F:great_work/state.py†L84-L115】【F:great_work/scholars.py†L18-L159】
- **Gap:** There is no system to keep the scholar pool within the desired size, trigger expedition sidecasts, progress careers, or publish public defection stories tied to memory changes.【F:great_work/service.py†L160-L217】【F:great_work/scholars.py†L162-L184】

## 2. Confidence Wagers, Reputation, and Recruitment Effects
- **Design intent:** Confidence wagers alter reputation according to the provided table and impose a recruitment cooldown (halved success chances for two ticks) after any “stake my career” claim, all within bounded reputation thresholds.【F:docs/HLD.md†L44-L116】
- **Implementation status:** Reputation deltas follow the wager table, but partial outcomes reuse half the reward and no cooldown or reputation-bound logic is applied; recruitment odds are unaffected because no recruitment system exists yet.【F:great_work/service.py†L118-L217】【F:great_work/config.py†L14-L58】
- **Gap:** Missing cooldown tracking, recruitment impact hooks, and enforcement of reputation thresholds or soft caps referenced in the design.【F:docs/HLD.md†L54-L116】【F:great_work/service.py†L192-L200】

## 3. Expedition Structure and Outcomes
- **Design intent:** Distinct expedition types (think tank, field, great project), prep modifiers, and prep-depth-dependent failure tables should produce sideways discoveries and social fallout.【F:docs/HLD.md†L57-L138】
- **Implementation status:** Expeditions are handled with a single queue/resolution path using shared modifiers and static sideways discovery text; there is no concept of expedition type, cost, or public social consequences beyond templated press releases.【F:great_work/service.py†L118-L217】【F:great_work/expeditions.py†L48-L103】
- **Gap:** Missing expedition typing, influence/reputation costs, dynamic sideways discovery content, and hooks for gossip or faction reactions after failures.【F:docs/HLD.md†L57-L138】【F:great_work/press.py†L21-L93】

## 4. Influence Economy and Faction Mechanics
- **Design intent:** Players earn and spend a five-vector influence score with soft caps tied to reputation, affecting recruitment and expedition logistics.【F:docs/HLD.md†L65-L138】
- **Implementation status:** Players are initialized with a five-key influence dict, but there are no mechanics to change influence, enforce caps, or apply faction requirements to actions.【F:great_work/service.py†L70-L155】【F:great_work/state.py†L49-L141】
- **Gap:** Influence accumulation, expenditure, faction checks on actions, and scaling caps remain unimplemented.【F:docs/HLD.md†L65-L138】

## 5. Press Artefacts and Public Record
- **Design intent:** Every action yields rich press artefacts (bulletins, manifestos, discovery reports or retractions, gossip), ideally with AI persona voices and persistent publication.【F:docs/HLD.md†L86-L266】【F:docs/HLD.md†L318-L354】
- **Implementation status:** Templates generate simple text for bulletins, manifestos, discovery reports, and gossip, but no retraction notices, persona-driven prose, or automated triggering of gossip; generated outputs are not persisted separately from the event log.【F:great_work/press.py†L11-L104】【F:great_work/service.py†L85-L190】
- **Gap:** Need persona-aware generation, support for retractions, gossip triggers for social events, and storage of press artefacts for public archives.【F:docs/HLD.md†L86-L266】【F:great_work/state.py†L117-L141】

## 6. Timing, Gazette Cadence, and Symposiums
- **Design intent:** Twice-daily Gazette digests process queued orders, while weekly symposiums enforce public stances within the Discord flow.【F:docs/HLD.md†L101-L280】【F:docs/HLD.md†L381-L386】
- **Implementation status:** A scheduler triggers digest resolution by calling expedition resolution and logs a placeholder symposium message; there is no order queue beyond expeditions, no symposium content, and no Discord integration for scheduled posts.【F:great_work/scheduler.py†L23-L43】【F:great_work/discord_bot.py†L19-L132】
- **Gap:** Need a broader order pipeline, Gazette publication to Discord, symposium event scripting, and integration with reputation/influence effects.【F:docs/HLD.md†L101-L280】

## 7. Data Model and Persistence
- **Design intent:** Persistence should cover players, scholars, factions, relationships, theories, expeditions, offers, events, press releases, and contracts, accessible via `/export_log`.【F:docs/HLD.md†L203-L346】【F:docs/HLD.md†L384-L385】
- **Implementation status:** SQLite stores only players, scholars, and events; there is an event export helper but no API or command to expose it, and other tables are absent.【F:great_work/state.py†L14-L141】【F:great_work/discord_bot.py†L110-L121】
- **Gap:** Missing storage for theories, expeditions, press artefacts, relationships, offers, and a Discord `/export_log` command as described.【F:docs/HLD.md†L203-L385】

## 8. Discord Command Surface and Admin Tools
- **Design intent:** Provide slash commands for submitting theories, wagers, recruitment, expeditions, conferences, status checks, exporting logs, plus an admin hotfix command.【F:docs/HLD.md†L248-L253】【F:docs/HLD.md†L384-L385】
- **Implementation status:** Only three commands exist (`/submit_theory`, `/launch_expedition`, `/resolve_expeditions`), and there is no admin or export command.【F:great_work/discord_bot.py†L33-L121】
- **Gap:** Need to implement the remaining player commands, status queries, export functionality, and at least one admin hotfix action.【F:docs/HLD.md†L248-L385】

## 9. LLM and Narrative Integration
- **Design intent:** Use LLM prompts per scholar for press releases and reactions with safety controls and batching strategies.【F:docs/HLD.md†L318-L369】
- **Implementation status:** Scholar reactions are formatted by substituting placeholders into static catchphrases; there is no LLM integration or safety layer.【F:great_work/service.py†L202-L216】【F:great_work/press.py†L60-L93】
- **Gap:** Implement persona-driven generation, batching, and moderation pipeline as outlined in the design.【F:docs/HLD.md†L318-L369】
