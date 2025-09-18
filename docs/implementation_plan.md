# Implementation Plan to Close Documented Gaps

## 1. Scholar Lifecycle and Defection Arcs
- Build mentorship and assignment actions that let players develop scholars, increment structured career tracks, and surface those beats during digest advancement with persistent records.【F:docs/HLD.md†L165-L213】【F:great_work/service.py†L536-L633】
- Extend sidecast follow-ups into branching arcs (e.g., mentorship offers, rival poaching, symposium invitations) so new scholars continue generating events beyond their introduction.【F:docs/HLD.md†L165-L213】【F:great_work/service.py†L440-L566】
- Expand defection follow-ups into multi-step pipelines that can trigger return offers, rival contracts, and additional press beyond a single gossip item.【F:docs/HLD.md†L171-L213】【F:great_work/service.py†L566-L633】

## 2. Confidence, Reputation, and Recruitment Effects
- Surface reputation thresholds and the wager table inside Discord (status panels, help text) so players understand gating and rewards without consulting configuration files.【F:docs/HLD.md†L44-L138】【F:great_work/discord_bot.py†L118-L150】
- Add forthcoming conference/wager commands that reuse `_require_reputation`, apply cooldown impacts, and archive outcomes with press for parity with expeditions and recruitment.【F:docs/HLD.md†L54-L138】【F:great_work/service.py†L214-L383】
- Provide admin-visible telemetry for cooldown progression and recruitment modifiers to support moderation and balancing.【F:docs/HLD.md†L44-L116】【F:great_work/service.py†L518-L566】

## 3. Expedition Depth and Sideways Fallout
- Translate sideways discovery strings into concrete state changes—faction reputation shifts, queued follow-up expeditions, or scholar memory updates—so partial successes alter gameplay.【F:docs/HLD.md†L77-L138】【F:great_work/service.py†L383-L506】
- Introduce expedition-type-specific aftermath hooks that publish bespoke gossip or faction reactions when catastrophic failures occur.【F:docs/HLD.md†L90-L138】【F:great_work/press.py†L12-L128】
- Track preparation depth per axis (think tank, expertise, site, political) when generating follow-up orders or modifiers to support richer differentiation.【F:docs/HLD.md†L101-L138】【F:great_work/models.py†L118-L149】

## 4. Influence Economy Balancing
- Create additional influence sinks/sources tied to symposium commitments, contracts, and offers so the five-vector economy remains dynamic between expeditions.【F:docs/HLD.md†L90-L213】【F:great_work/service.py†L506-L633】
- Expose cap feedback in Discord (e.g., notifications when a faction hits its ceiling) and record the event log entries for transparency.【F:docs/HLD.md†L90-L138】【F:great_work/discord_bot.py†L118-L150】
- Persist faction standings or obligations alongside influence so future mechanics (alliances, embargoes) have stored context.【F:docs/HLD.md†L203-L346】【F:great_work/state.py†L18-L210】

## 5. Press Artefacts and Narrative Delivery
- Layer persona-driven LLM generation, batching, and moderation guards onto the existing press templates to achieve the intended narrative voice.【F:docs/HLD.md†L214-L369】【F:great_work/press.py†L12-L128】
- Expand gossip triggers to cover recruitment fallout, symposium drama, and extended defection arcs, ensuring social beats produce artefacts beyond current sidecasts.【F:docs/HLD.md†L214-L354】【F:great_work/service.py†L440-L633】
- Automate Gazette publishing into public Discord channels (or a web archive) using the stored press records instead of manual command responses.【F:docs/HLD.md†L214-L280】【F:great_work/scheduler.py†L12-L64】

## 6. Gazette Cadence and Symposium Flow
- Wire the scheduler publisher into Discord, formatting twice-daily digests that summarise the releases produced by `advance_digest` and expedition resolution.【F:docs/HLD.md†L101-L280】【F:great_work/scheduler.py†L34-L53】
- Implement the symposium content pipeline (topic selection, mandated responses, consequence calculation) and schedule reminder press leading into the weekly event.【F:docs/HLD.md†L249-L386】【F:great_work/service.py†L506-L633】
- Support queuing of non-expedition orders (mentorship, conferences) that process during digest ticks alongside existing expedition flows.【F:docs/HLD.md†L101-L213】【F:great_work/service.py†L440-L633】

## 7. Command Surface and Admin Tooling
- Deliver the remaining slash commands (`/wager`, `/conference`, defection/admin tools) mapped to the service APIs, including validation feedback and archived press output.【F:docs/HLD.md†L248-L386】【F:great_work/discord_bot.py†L32-L176】
- Provide audited admin overrides (reputation/influence adjustment, order cancellation) that append to the event log for transparency.【F:docs/HLD.md†L248-L386】【F:great_work/state.py†L94-L210】
- Offer richer status cards (queued orders, cooldown timers, thresholds) either as Discord embeds or attachments for player clarity.【F:docs/HLD.md†L248-L286】【F:great_work/service.py†L472-L566】

## 8. Data Export and Safety Infrastructure
- Activate the existing offers table with workflows for drafting, issuing, and resolving faction contracts so defection tooling has persistent context.【F:docs/HLD.md†L203-L346】【F:great_work/state.py†L58-L210】
- Extend `/export_log` to support pagination/attachments and include newly introduced lifecycle events (symposium outcomes, mentorship beats).【F:docs/HLD.md†L248-L386】【F:great_work/discord_bot.py†L142-L176】
- Integrate safety tooling—blocklists, rate limits, manual review hooks—for the forthcoming LLM narrative generation layer.【F:docs/HLD.md†L318-L369】【F:great_work/service.py†L613-L633】
