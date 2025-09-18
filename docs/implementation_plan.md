# Implementation Plan to Close Documented Gaps

## 1. Scholar Lifecycle and Defection Arcs
- Introduce roster curation routines (retire low-activity scholars, graduate mentored juniors) so the population stays within the 20–30 window while making room for sidecasts that already spawn from expeditions.【F:docs/HLD.md†L165-L213】【F:great_work/service.py†L463-L551】
- Model mentorship/career progression beats that run during digest advancement, updating scholar careers, logging Gazette notes, and persisting progression state alongside existing relationship data.【F:docs/HLD.md†L165-L213】【F:great_work/state.py†L22-L233】
- Extend defection handling to schedule follow-up arcs (e.g., grudges, return offers) that leverage stored scars and relationships to influence future decisions and press.【F:docs/HLD.md†L171-L213】【F:great_work/service.py†L370-L428】

## 2. Confidence, Reputation, and Recruitment Effects
- Gate public actions (recruitment, expeditions, high-stakes wagers) behind the documented reputation thresholds and surface clear errors through the Discord bot when requirements are unmet.【F:docs/HLD.md†L44-L116】【F:great_work/service.py†L228-L368】【F:great_work/discord_bot.py†L14-L110】
- Wire `advance_digest` into the scheduled digest loop so recruitment cooldowns decay automatically, and display cooldown status in status exports to make the mechanic legible.【F:docs/HLD.md†L101-L138】【F:great_work/service.py†L430-L437】【F:great_work/scheduler.py†L1-L43】
- Add a `/recruit` command (plus admin overrides) that calls the existing recruitment service, handles success/failure messaging, and records Discord-facing feedback matching the Gazette output.【F:docs/HLD.md†L248-L286】【F:great_work/service.py†L304-L368】【F:great_work/discord_bot.py†L14-L110】

## 3. Expedition Depth and Sideways Fallout
- Split failure tables and sideways discovery copy per expedition type and prep depth, adding bespoke gossip/faction reactions for catastrophic results and integrating them with the press archive.【F:docs/HLD.md†L77-L138】【F:great_work/expeditions.py†L1-L74】【F:great_work/press.py†L14-L122】
- Expand `ExpeditionPreparation` (and Discord command args) to capture think tank, expertise, site, and political tracks individually while enforcing the influence costs/requirements for each expedition type.【F:docs/HLD.md†L104-L138】【F:great_work/models.py†L118-L155】【F:great_work/service.py†L158-L551】【F:great_work/discord_bot.py†L36-L110】
- Create post-resolution hooks that translate sideways discoveries into faction reputation swings, scholar memories, or follow-on orders so partial results still move the narrative state forward.【F:docs/HLD.md†L77-L138】【F:great_work/service.py†L284-L551】

## 4. Influence Economy Balancing
- Implement soft caps that scale with reputation and clamp `Player.influence` adjustments to maintain the intended curve, adding feedback when players hit faction ceilings.【F:docs/HLD.md†L90-L138】【F:great_work/models.py†L86-L117】【F:great_work/service.py†L490-L505】
- Add additional influence sinks and sources (symposium commitments, contract upkeep, defection fallout) that call into `GameService` so the five-vector economy matters outside expeditions and recruitment.【F:docs/HLD.md†L90-L213】【F:great_work/service.py†L304-L551】
- Surface current influence totals and caps via status exports to give players visibility into the economy before spending.【F:docs/HLD.md†L248-L286】【F:great_work/state.py†L103-L160】

## 5. Press Artefacts and Narrative Delivery
- Layer persona/LLM generation on top of the existing press templates, including batching and moderation safeguards, to reach the intended narrative tone.【F:docs/HLD.md†L214-L369】【F:great_work/service.py†L553-L569】【F:great_work/press.py†L14-L122】
- Trigger gossip and follow-up press for recruitment failures, defection aftermath, and symposium drama so social events produce artefacts beyond the current sidecast/recruitment hooks.【F:docs/HLD.md†L214-L266】【F:great_work/service.py†L304-L551】
- Expose the press archive through Discord (e.g., `/gazette` history) and `/export_log`, reusing the stored `press_releases` records and adding pagination where needed.【F:docs/HLD.md†L248-L386】【F:great_work/state.py†L22-L233】【F:great_work/discord_bot.py†L14-L110】

## 6. Gazette Cadence and Symposium Flow
- Update the scheduler to call `advance_digest` before publishing Gazette summaries, and push digest/symposium press directly into configured Discord channels instead of logging locally.【F:docs/HLD.md†L101-L280】【F:great_work/service.py†L228-L437】【F:great_work/scheduler.py†L1-L43】
- Build a symposium content pipeline (topic selection, required responses, consequence calculation) that interacts with influence/reputation adjustments and issues reminder press.【F:docs/HLD.md†L249-L386】【F:great_work/service.py†L228-L437】
- Allow players to queue non-expedition orders during the digest window (e.g., mentorship actions) and ensure they flow through the same scheduled processing path.【F:docs/HLD.md†L101-L213】【F:great_work/service.py†L430-L551】

## 7. Command Surface and Admin Tooling
- Add slash commands for recruitment, wagers, conferences/symposium stances, status summaries, and `/export_log`, mapping each to existing or newly built service methods and embedding validation feedback.【F:docs/HLD.md†L248-L386】【F:great_work/service.py†L228-L551】【F:great_work/discord_bot.py†L14-L110】
- Provide an admin hotfix command (e.g., adjust reputation/influence, resolve stuck orders) with auditing to the event/press logs for transparency.【F:docs/HLD.md†L248-L386】【F:great_work/state.py†L103-L233】
- Publish concise status cards through Discord showing reputation, influence, cooldowns, and pending orders by reading from the persisted state.【F:docs/HLD.md†L248-L286】【F:great_work/state.py†L103-L233】

## 8. Data Export and Safety Infrastructure
- Implement `/export_log` and related data pulls that stream events and press releases using the existing persistence tables, including pagination and file attachments where appropriate.【F:docs/HLD.md†L248-L386】【F:great_work/state.py†L186-L233】
- Add schema support and workflows for faction offers/contracts so defection pipelines can queue offers before evaluation, complementing the `offers` table stub.【F:docs/HLD.md†L203-L346】【F:great_work/state.py†L71-L233】
- Integrate moderation filters, rate limits, and batching for upcoming LLM-powered press hooks to align with the safety guidance.【F:docs/HLD.md†L318-L369】【F:great_work/service.py†L553-L569】
