# Implementation Plan to Close Documented Gaps

## 1. Scholar Lifecycle and Defection Arcs
- Add mentorship and placement actions that queue during digests, update scholar career state, and persist mentorship events so career progression is player-driven rather than automatic ticks.【F:docs/HLD.md†L145-L177】【F:great_work/service.py†L617-L686】
- Extend follow-up handling to support multi-step defection arcs (return offers, counter-offers, rival contracts) by storing stateful payloads and emitting additional press at each step.【F:docs/HLD.md†L165-L213】【F:great_work/service.py†L650-L686】【F:great_work/service.py†L728-L759】
- Expand sidecast generation to schedule further events (mentorship invitations, faction checks) so new scholars continue surfacing in gameplay instead of ending after a single gossip item.【F:docs/HLD.md†L165-L213】【F:great_work/service.py†L728-L759】

## 2. Confidence, Conferences, and Wager UX
- Implement `/conference` and related wager commands in the Discord bot, mirroring existing expedition/recruitment validation and routing requests through the service layer.【F:docs/HLD.md†L90-L138】【F:great_work/discord_bot.py†L114-L324】
- Add a conference resolution service that archives press, adjusts cooldowns, and records faction responses using the existing wager tables and reputation thresholds.【F:docs/HLD.md†L90-L138】【F:great_work/service.py†L214-L392】【F:great_work/press.py†L61-L96】
- Surface admin-visible telemetry for cooldown progress and recruitment modifiers via enhanced status/log exports to help moderators tune the wager economy.【F:docs/HLD.md†L44-L116】【F:great_work/service.py†L468-L505】【F:great_work/discord_bot.py†L236-L301】

## 3. Expedition Sideways Outcomes
- Translate sideways discoveries into concrete state changes—queued follow-up orders, faction influence shifts, or scholar memory updates—rather than storing text-only flavour.【F:docs/HLD.md†L90-L138】【F:great_work/service.py†L244-L307】【F:great_work/service.py†L728-L759】
- Introduce expedition-type-specific aftermath hooks that publish bespoke gossip or faction reactions when catastrophic failures occur.【F:docs/HLD.md†L57-L138】【F:great_work/press.py†L61-L96】
- Track preparation depth per axis when generating downstream orders so deep preparation unlocks bespoke narrative threads and modifiers.【F:docs/HLD.md†L101-L138】【F:great_work/models.py†L122-L135】

## 4. Influence Economy Enhancements
- Create new influence sinks (symposium commitments, contracts, faction offers) that consume stored influence vectors and record the resulting events for auditability.【F:docs/HLD.md†L104-L213】【F:great_work/service.py†L677-L738】【F:great_work/state.py†L18-L417】
- Notify players when approaching soft caps and persist faction standing data beyond influence to prepare for alliances or embargo mechanics.【F:docs/HLD.md†L90-L213】【F:great_work/service.py†L677-L772】【F:great_work/discord_bot.py†L236-L254】
- Activate the `offers` table by wiring contract workflows (draft, issue, resolve) through the service and Discord layers.【F:docs/HLD.md†L203-L346】【F:great_work/state.py†L77-L212】【F:great_work/service.py†L394-L466】

## 5. Press Artefacts and Public Archive
- Layer persona-driven generation (LLM prompts, batching, moderation) on top of the existing press templates to achieve the narrative tone described in the design.【F:docs/HLD.md†L214-L369】【F:great_work/press.py†L20-L145】
- Generate multiple artefacts per major action (bulletins, manifestos, reports, gossip) and publish them into a durable archive beyond Discord, such as a web view or attachment feed.【F:docs/HLD.md†L214-L354】【F:great_work/service.py†L125-L513】【F:great_work/scheduler.py†L20-L59】
- Automate Gazette exports so digests are stored externally (S3, static site) in addition to Discord postings, ensuring permanent public access.【F:docs/HLD.md†L214-L280】【F:great_work/state.py†L366-L417】【F:great_work/discord_bot.py†L274-L301】

## 6. Gazette Cadence and Symposium Flow
- Build the symposium topic pipeline (selection, reminder press, response deadlines) and integrate outcomes into the digest loop with stored results and press artefacts.【F:docs/HLD.md†L249-L386】【F:great_work/scheduler.py†L32-L56】【F:great_work/service.py†L515-L553】
- Allow non-expedition orders (mentorship, conferences) to queue and resolve during digests alongside existing expedition flows.【F:docs/HLD.md†L101-L213】【F:great_work/service.py†L515-L553】
- Enrich scheduled posts with digest headers, pinned summaries, and fallback archiving when channels are missing so cadence remains reliable.【F:docs/HLD.md†L101-L280】【F:great_work/scheduler.py†L20-L59】

## 7. Command Surface and Admin Tooling
- Deliver remaining slash commands (`/conference`, defection/admin overrides) with validation feedback, press output, and audit logging.【F:docs/HLD.md†L248-L386】【F:great_work/discord_bot.py†L114-L324】【F:great_work/service.py†L394-L466】
- Provide audited admin overrides for reputation/influence adjustment and order cancellation, storing events and press artefacts where appropriate.【F:docs/HLD.md†L248-L386】【F:great_work/state.py†L255-L310】
- Offer richer status cards (queued orders, cooldown timers, thresholds) as embeds or attachments for player clarity.【F:docs/HLD.md†L248-L286】【F:great_work/service.py†L468-L505】【F:great_work/discord_bot.py†L236-L301】

## 8. Narrative Safety and Export Improvements
- Integrate moderation safeguards—blocklists, rate limits, manual review hooks—for new narrative generation paths before exposing them publicly.【F:docs/HLD.md†L318-L369】【F:great_work/press.py†L20-L145】【F:great_work/service.py†L394-L466】
- Enhance `/export_log` with pagination/attachments and include new lifecycle events so external auditing covers symposium and mentorship beats.【F:docs/HLD.md†L248-L386】【F:great_work/discord_bot.py†L289-L301】【F:great_work/service.py†L486-L513】
- Instrument telemetry that tracks scholar mentorship outcomes, defection arcs, and shared press releases to measure success criteria.【F:docs/HLD.md†L318-L369】【F:great_work/service.py†L617-L686】
