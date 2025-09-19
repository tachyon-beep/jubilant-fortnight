# Gap Analysis: High-Level Design vs. Current Implementation

Last Updated: 2025-09-19 (Post-Sprint 1 Update)

## 1. Scholar Lifecycle and Memory

- **Design intent:** Maintain a roster of 20–30 memorable scholars blending handcrafted legends with procedurally generated additions, spawn sidecast scholars from expeditions, nurture mentorship-driven career growth, and track defections with scars and public fallout.【F:docs/HLD.md†L24-L177】
- **Implementation status:** `GameService` seeds the roster on boot, enforces the 20–30 headcount window by generating or retiring scholars, archives the resulting events, and during each digest advances careers automatically, resolves scheduled follow-ups, and spawns sidecasts when expeditions succeed.【F:great_work/service.py†L60-L61】【F:great_work/service.py†L581-L616】【F:great_work/service.py†L728-L759】
- **Gap:** ~~Mentorship system now fully implemented with `/mentor` and `/assign_lab` commands~~. Sidecasts still conclude after a single gossip artefact, and follow-up resolutions only adjust feelings instead of progressing the multi-step defection arcs outlined in the design.【F:docs/HLD.md†L145-L213】【F:great_work/service.py†L617-L686】

## 2. Confidence Wagers, Reputation, and Recruitment Effects

- **Design intent:** Confidence wagers must follow the tuned reward/penalty table, clamp reputation within bounds, and impose recruitment cooldowns on high-stakes wagers while recruitment odds reflect cooldowns, faction influence, and unlock thresholds.【F:docs/HLD.md†L44-L138】
- **Implementation status:** Reputation changes use the configured wager table and bounds, expedition and recruitment commands enforce reputation thresholds, recruitment odds incorporate cooldown and influence modifiers, and `/status` plus `/wager` expose the thresholds, bounds, and stake payouts in Discord.【F:great_work/service.py†L214-L392】【F:great_work/service.py†L468-L505】【F:great_work/discord_bot.py†L236-L272】
- **Gap:** ~~Conference system now fully implemented with `/conference` command, `launch_conference()` and `resolve_conferences()` service methods, and `conferences` table~~. Public wager mechanics fully operational.【F:docs/HLD.md†L90-L138】【F:great_work/discord_bot.py†L296-L332】【F:great_work/service.py†L597-L639】

## 3. Expedition Structure and Outcomes

- **Design intent:** Each expedition type should apply tailored costs, prep modifiers, and depth-aware failure tables that yield sideways discoveries with gameplay repercussions such as faction swings, gossip, or queued orders.【F:docs/HLD.md†L57-L138】
- **Implementation status:** Expedition launches deduct influence by type, persist preparation details, and resolve through an `ExpeditionResolver` that rolls d100, applies modifiers, consults depth-specific failure tables, and records the outcome along with reaction text and sideways flavour. **Sprint 2 Update:** Sideways discoveries now trigger mechanical effects via `SidewaysEffect` system.【F:great_work/service.py†L170-L318】【F:great_work/expeditions.py†L60-L240】【F:great_work/data/failure_tables.yaml†L1-L80】【F:great_work/press.py†L61-L96】
- **Gap:** ~~Sideways discoveries remain narrative flavour with no faction effects~~ **[RESOLVED - Sprint 2]**. Deep preparation narrative beats still primarily text-based.【F:docs/HLD.md†L90-L138】【F:great_work/service.py†L1499-L1638】

### 3.1 Great Projects - Status

- **Design intent:** Full implementation of Great Projects as large science efforts that unlock new research domains.【F:docs/HLD.md†L61】
- **Implementation status:** Great Projects are fully implemented and accessible via Discord commands with costs/rewards and reputation thresholds.【F:great_work/service.py†L65-L72】【F:great_work/expeditions.py†L60-L116】【F:great_work/data/settings.yaml†L26】
- **Gap:** None - feature is correctly implemented as designed.

## 4. Influence Economy and Faction Mechanics

- **Design intent:** Influence should operate as a five-dimensional economy with soft caps tied to reputation and faction requirements across key actions, supported by additional sinks such as symposium commitments and contracts.【F:docs/HLD.md†L90-L213】
- **Implementation status:** Player influence is persisted per faction, capped using reputation-driven limits, modified by expedition costs/rewards and recruitment success, and surfaced through the `/status` command.【F:great_work/service.py†L170-L392】【F:great_work/service.py†L677-L772】【F:great_work/discord_bot.py†L236-L254】
- **Gap:** Outside expeditions and recruitment there are no influence sinks or faction-gated activities, leaving the economy far simpler than the symposium, contract, and offer loops promised in the design.【F:docs/HLD.md†L104-L213】【F:great_work/service.py†L677-L738】

## 5. Press Artefacts and Public Record

- **Design intent:** Every move should produce persona-driven press artefacts that persist in a public archive—bulletins, manifestos, discoveries, retractions, gossip, recruitment notes, defection wires—and stay publicly accessible.【F:docs/HLD.md†L86-L354】
- **Implementation status:** Templated generators create press for theories, expeditions, recruitment, and defections; `GameService` archives releases in SQLite; and Discord commands let players list Gazette entries or export logs.【F:great_work/press.py†L20-L145】【F:great_work/service.py†L125-L513】【F:great_work/state.py†L366-L417】【F:great_work/discord_bot.py†L274-L301】
- **Gap:** Copy uses static templates without LLM persona voice or moderation safeguards, Gazette digests only reach Discord channels without permanent web archive, and most actions emit single artefacts instead of layered bulletins/manifestos/reports.【F:docs/HLD.md†L214-L354】【F:great_work/scheduler.py†L41-L48】【F:great_work/press.py†L20-L145】

### 5.1 Public archive availability

- **Design intent:** Keep a permanent, public, citable archive beyond Discord.【F:docs/HLD.md†L214-L354】
- **Implementation status:** Press is archived to SQLite and can be exported via `/export_log`, but there is no external static archive or web view.【F:great_work/state.py†L366-L417】【F:great_work/discord_bot.py†L289-L301】
- **Gap:** Introduce an exporter (e.g., static site or attachment bundles) to satisfy permanence and accessibility goals.

## 6. Timing, Gazette Cadence, and Symposiums

- **Design intent:** Twice-daily Gazette digests should advance cooldowns, timeline years, and queued orders before publishing to Discord, while weekly symposiums run structured topics with mandatory responses.【F:docs/HLD.md†L101-L386】
- **Implementation status:** The background scheduler triggers digests at configured times, calling `advance_digest` to age cooldowns, maintain the roster, progress careers, resolve follow-ups, and then resolve pending expeditions before broadcasting to the Gazette channel; a weekly symposium heartbeat posts a placeholder announcement.【F:great_work/scheduler.py†L20-L59】【F:great_work/discord_bot.py†L89-L113】【F:great_work/service.py†L515-L686】
- **Gap:** ~~Symposium voting now implemented with `/symposium_vote` command and `vote_symposium()` method, `symposium_topics` and `symposium_votes` tables added~~. Topic selection system now functional. Digest processing now includes mentorship and conference resolution.【F:docs/HLD.md†L101-L280】【F:great_work/discord_bot.py†L334-L355】【F:great_work/service.py†L799-L858】

### 6.1 Non-expedition order batching

- **Design intent:** Orders like mentorships and conferences batch into digests.【F:docs/HLD.md†L101-L213】
- **Implementation status:** Only expedition resolution and follow-ups are batched; there is no queue for other order types yet.【F:great_work/service.py†L515-L686】
- **Gap:** ~~Generic order handling now implemented for mentorship and conference flows with proper queue and resolution methods~~.

## 7. Data Model and Persistence

- **Design intent:** Persist players, scholars, relationships, theories, expeditions, offers, press artefacts, and events with exports available through a bot command.【F:docs/HLD.md†L203-L385】
- **Implementation status:** The SQLite schema stores all listed entities, including offers and follow-ups, and the service exposes both the press archive and `/export_log` command for retrieval.【F:great_work/state.py†L18-L417】【F:great_work/service.py†L486-L513】【F:great_work/discord_bot.py†L289-L301】
- **Gap:** Offers table exists but is still unused (no INSERT or SELECT operations), contracts field exists but unused, faction standings beyond influence remain absent. ~~Mentorship and symposium lifecycle events now properly persisted with new tables (`mentorships`, `symposium_topics`, `symposium_votes`)~~.【F:docs/HLD.md†L203-L346】【F:great_work/state.py†L98-L141】

## 8. Discord Command Surface and Admin Tools

- **Design intent:** Provide slash commands for theories, wagers, recruitment, expeditions, conferences, status checks, log exports, and at least one admin hotfix interface.【F:docs/HLD.md†L248-L386】
- **Implementation status:** The bot offers slash commands for theory submission, expedition launch/resolution, recruitment, wager lookups, status, Gazette browsing, log export, and table-talk, and the scheduler mirrors gameplay updates into the configured channels.【F:great_work/discord_bot.py†L114-L324】【F:great_work/scheduler.py†L20-L59】
- **Gap:** ~~All previously missing commands now implemented: `/conference`, `/mentor`, `/assign_lab`, `/symposium_vote`, and `/gw_admin` command group with full admin functionality~~. Defection mechanics exist in service layer (evaluate_defection_offer) but still have no direct Discord interface for players (admin can force defections).【F:docs/HLD.md†L248-L386】【F:great_work/discord_bot.py†L248-L543】【F:great_work/service.py†L914-L1148】

### 8.1 Credentials and application configuration

- **Design intent:** Bot setup assumes proper Discord app configuration but does not specify runtime variables.【F:docs/HLD.md†L248-L286】
- **Implementation status:** The bot now supports `DISCORD_APP_ID` and posts to configured channels; tokens and keys are provided via environment variables, not documented in HLD.【F:great_work/discord_bot.py†L69-L113】
- **Gap:** Add a short deployment/config appendix in docs to align with the code’s environment variable surface (token, app id, channel ids).

## 9. LLM and Narrative Integration

- **Design intent:** Generate press and reactions through persona-driven LLM prompts with batching and moderation safeguards.【F:docs/HLD.md†L318-L369】
- **Implementation status:** All press remains templated string substitution with no LLM calls or safety layers.【F:great_work/press.py†L20-L145】
- **Gap:** The persona prompt pipeline, batching strategies, and moderation checks still need to be introduced to match the intended narrative richness.【F:docs/HLD.md†L318-L369】【F:great_work/press.py†L20-L145】

## Summary of Major Gaps

### Critical Missing Features

1. ~~**Mentorship System**: Fully implemented with `/mentor` and `/assign_lab` commands, `queue_mentorship()` and `assign_lab()` service methods~~
2. ~~**Conference Mechanics**: Fully implemented with `/conference` command, database table, and resolution logic~~
3. ~~**Symposium Implementation**: Voting system implemented with `/symposium_vote`, topics and voting tables~~
4. **Public Archive**: No web presence or permanent archive beyond Discord exports
5. ~~**Admin Tools**: Fully implemented `/gw_admin` command group with all moderation/hotfix commands~~
6. **LLM Integration**: Complete absence of AI-driven narrative generation

### Correctly Implemented Features

1. **Great Projects**: Fully implemented as designed
2. **Influence Economy**: Five-faction system with reputation-based soft caps (base 6 + 0.2 per reputation point)
3. **Confidence Wagers**: Complete with reputation stakes (suspect +2/-1, certain +5/-7, stake_my_career +15/-25) and cooldowns
4. **Expedition Resolution**: d100 system with modifiers, failure tables (shallow/deep), and sideways discoveries
5. **Mentorship System**: Player-driven mentorship with career track assignment
6. **Conference System**: Public wager conferences with full resolution mechanics
7. **Symposium Voting**: Topic selection and community voting system
8. **Admin Tools**: Complete moderation toolkit with reputation/influence adjustments and force actions

### Partially Complete

1. **Defection Arcs**: Single-step follow-ups only, missing multi-stage negotiations
2. ~~**Order Batching**: Now includes mentorships and conferences along with expeditions~~
3. **Press Generation**: Single artefacts per action, not layered bulletins/manifestos/reports
4. ~~**Sideways Discoveries**: Mechanical effects fully implemented via SidewaysEffect system~~ **[COMPLETED - Sprint 2]**

## Additional Implementation Details

### Database Infrastructure

- **Offers Table**: Created but completely unused - no code references INSERT or SELECT operations
- **Followups Table**: Actively used for defection grudges and recruitment follow-ups with delays
- **Timeline Table**: Properly tracks game year progression based on real-time days
- **Relationships Table**: Stores scholar-to-scholar and scholar-to-player relationships

### Service Layer Capabilities

- **Defection Evaluation**: `evaluate_defection_offer()` method exists but not exposed via Discord (admin can force via `/gw_admin force_defection`)
- **Career Progression**: `_progress_careers()` runs automatically, plus player-driven via `queue_mentorship()` and `assign_lab()`
- **Influence Management**: `_apply_influence_change()` enforces soft caps correctly
- **Roster Management**: `_ensure_roster()` maintains 20-30 scholar count automatically
- **Conference Management**: `launch_conference()` and `resolve_conferences()` handle public wagers
- **Symposium System**: `vote_symposium()` and topic selection fully operational
- **Admin Functions**: `admin_adjust_reputation()`, `admin_adjust_influence()`, `admin_force_defection()`, `admin_cancel_expedition()`

### Configuration Details

- **Reputation Bounds**: -50 to +50 as designed
- **Influence Caps**: Base 6 + 0.2 per reputation point
- **Expedition Thresholds**: think_tank (-5 rep), field (0 rep), great_project (10 rep)
- **Cooldown Delays**: defection_grudge (2 days), defection_return (3 days), recruitment_grudge (1 day)
