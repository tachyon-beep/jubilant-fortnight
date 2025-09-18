# Requirement Decomposition

## Functional Requirements

### Core Gameplay Loop and Transparency

| Requirement | Status | Notes |
| --- | --- | --- |
| Provide an asynchronous multiplayer experience supporting between four and eight concurrent players. | Partially Implemented | Discord slash commands let multiple players act asynchronously, but there is no explicit enforcement of player counts or turn management yet.【F:great_work/discord_bot.py†L32-L176】 |
| Deliver all player moves through a Discord bot. | Partially Implemented | Core actions (theories, expeditions, recruitment, status, archives) are exposed via slash commands, while defection handling and admin moves remain service-only.【F:great_work/discord_bot.py†L32-L176】【F:great_work/service.py†L347-L440】 |
| Make every action publicly visible to all participants. | Partially Implemented | Major moves emit press releases and events, but Gazette digests are not automatically published to public channels and some responses remain ephemeral.【F:great_work/service.py†L120-L633】【F:great_work/scheduler.py†L12-L64】 |
| Advance the shared narrative timeline by one in-game year for each real-world day that passes. | Implemented | Digest advancement now calls into timeline persistence to convert elapsed real days into in-world years, emitting Gazette updates whenever the calendar rolls forward.【F:great_work/service.py†L480-L528】【F:great_work/state.py†L38-L174】 |

### Scholar Management

| Requirement | Status | Notes |
| --- | --- | --- |
| Maintain a persistent roster of 20 to 30 scholars. | Implemented | `GameService` enforces minimum and maximum roster sizes, spawning or retiring scholars as needed during digest advancement.【F:great_work/service.py†L440-L518】 |
| Track memories, personalities, and interrelationships for each scholar. | Implemented | Scholar models persist memory facts, feelings, scars, and relationships through SQLite tables and helper methods.【F:great_work/models.py†L12-L112】【F:great_work/state.py†L58-L160】 |
| Support handcrafted scholars alongside procedurally generated scholars. | Implemented | The repository loads authored templates and generates new scholars deterministically when filling the roster or spawning sidecasts.【F:great_work/scholars.py†L14-L116】 |
| Enable scholars to emerge through defined lifecycle events. | Implemented | Successful expeditions can spawn sidecast scholars who join the roster with recorded press.【F:great_work/service.py†L480-L518】 |
| Allow scholars to receive mentorship from other scholars or players. | Not Implemented | No mentorship or assignment commands exist yet; digest advancement only progresses automatic career ticks without player intervention.【F:great_work/service.py†L518-L633】 |
| Evaluate defection and return events for scholars using probabilistic logic. | Partially Implemented | Defection probability and event logging are implemented, but return arcs and chained offers are still limited to simple follow-up gossip.【F:great_work/scholars.py†L118-L180】【F:great_work/service.py†L347-L440】【F:great_work/service.py†L566-L633】 |

### Confidence Wagering

| Requirement | Status | Notes |
| --- | --- | --- |
| Require players to declare confidence levels before resolving an action. | Implemented | Theory submissions and expeditions demand explicit `ConfidenceLevel` selections, aligning with the wager system.【F:great_work/service.py†L120-L286】【F:great_work/discord_bot.py†L45-L114】 |
| Deduct reputation stakes that scale with the declared confidence level. | Implemented | Outcome resolution applies the configured wager table and clamps reputation within bounds.【F:great_work/service.py†L286-L383】【F:great_work/config.py†L10-L53】 |
| Apply a cooldown penalty to any player who declares a high-stakes wager. | Implemented | Staking a career enforces recruitment cooldowns that decay during digests and influence recruitment odds.【F:great_work/service.py†L286-L566】 |

### Expeditions and Outcomes

| Requirement | Status | Notes |
| --- | --- | --- |
| Offer think tank expeditions as a selectable option. | Implemented | Discord commands and service logic accept `think_tank` expeditions with tailored costs and rewards.【F:great_work/discord_bot.py†L59-L114】【F:great_work/service.py†L214-L383】 |
| Offer field expeditions as a selectable option. | Implemented | Field expeditions are handled alongside other types using the same queue and resolver flow.【F:great_work/service.py†L214-L383】 |
| Offer deferred Great Projects as a selectable option. | Implemented | The resolver and cost tables include `great_project`, though narrative gating is still up to gameplay direction.【F:great_work/service.py†L214-L383】【F:great_work/expeditions.py†L12-L86】 |
| Resolve expedition outcomes using a d100 recipe. | Implemented | `ExpeditionResolver` rolls d100 and computes modifiers before determining outcomes.【F:great_work/expeditions.py†L38-L86】 |
| Incorporate preparation modifiers into expedition resolution. | Implemented | Preparation inputs contribute to the modifier sum applied during resolution.【F:great_work/models.py†L118-L149】【F:great_work/expeditions.py†L38-L86】 |
| Incorporate expertise modifiers into expedition resolution. | Implemented | Expertise bonuses are part of the `ExpeditionPreparation` data used in modifier calculations.【F:great_work/models.py†L118-L149】 |
| Incorporate friction modifiers into expedition resolution. | Implemented | Site and political friction values are included in the aggregated modifier.【F:great_work/models.py†L118-L149】 |
| Define success bands for expedition results. | Implemented | Resolver thresholds map final scores to failure, partial, success, and landmark bands.【F:great_work/expeditions.py†L38-L86】 |
| Define failure bands for expedition results. | Implemented | Failure tables provide typed outcomes per expedition and depth when rolls fall below success thresholds.【F:great_work/expeditions.py†L12-L86】【F:great_work/data/failure_tables.yaml†L1-L44】 |
| Scale failure consequence tables based on the depth of pre-expedition preparation. | Implemented | Separate shallow/deep tables and sideways discovery entries are selected by depth.【F:great_work/data/failure_tables.yaml†L1-L44】 |

### Influence Economy

| Requirement | Status | Notes |
| --- | --- | --- |
| Track each player's influence as a five-dimensional faction vector. | Implemented | Player records persist influence by faction in SQLite and expose it via status commands.【F:great_work/state.py†L24-L112】【F:great_work/discord_bot.py†L118-L150】 |
| Tie the soft cap for each influence dimension to the player's reputation score. | Implemented | Influence adjustments clamp against a cap derived from reputation-driven settings.【F:great_work/service.py†L506-L566】【F:great_work/config.py†L10-L53】 |
| Prevent players from monopolizing a single faction by enforcing soft caps. | Implemented | `_apply_influence_change` enforces the computed cap when adding influence, limiting single-faction hoarding.【F:great_work/service.py†L506-L566】 |

### Press Artifacts and Gazette Cadence

| Requirement | Status | Notes |
| --- | --- | --- |
| Auto-generate a bulletin for every recorded action. | Partially Implemented | Theory submissions and key events generate press, but not every event (e.g., admin actions) has a dedicated bulletin yet.【F:great_work/service.py†L120-L633】 |
| Auto-generate a manifest for every recorded action. | Partially Implemented | Expedition launches create research manifestos, though other action types reuse different templates or none at all.【F:great_work/service.py†L214-L383】【F:great_work/press.py†L12-L128】 |
| Auto-generate a report for every recorded action. | Partially Implemented | Expedition resolutions produce discovery or retraction reports, but other gameplay actions may only log events without reports.【F:great_work/service.py†L286-L440】【F:great_work/press.py†L12-L128】 |
| Auto-generate a gossip item for every recorded action. | Partially Implemented | Recruitment, follow-ups, and promotions emit gossip, yet numerous actions remain gossip-free today.【F:great_work/service.py†L347-L633】【F:great_work/press.py†L12-L128】 |
| Publish Gazette digests twice per real day summarizing actions. | Partially Implemented | The scheduler fires twice daily and processes digests, but publishing still depends on providing an external publisher hook.【F:great_work/scheduler.py†L12-L64】 |
| Host weekly Symposium threads to highlight notable developments. | Partially Implemented | A scheduled symposium heartbeat exists, but no topic selection or participation mechanics are implemented.【F:great_work/scheduler.py†L45-L64】 |

### Discord UX and Commands

| Requirement | Status | Notes |
| --- | --- | --- |
| Expose gameplay interactions through the `#orders` channel. | Not Implemented | Channel routing is not automated; commands respond in-place without channel-specific dispatch.【F:great_work/discord_bot.py†L32-L176】 |
| Expose gameplay interactions through the `#gazette` channel. | Not Implemented | Gazette publications rely on manual command responses rather than targeted channel posts.【F:great_work/discord_bot.py†L104-L176】【F:great_work/scheduler.py†L12-L64】 |
| Expose gameplay interactions through the `#table-talk` channel. | Not Implemented | No functionality differentiates table-talk output from other channels yet.【F:great_work/discord_bot.py†L32-L176】 |
| Provide the `/submit_theory` slash command. | Implemented | Command registered and wired to `GameService.submit_theory`.【F:great_work/discord_bot.py†L32-L74】 |
| Provide the `/wager` slash command. | Not Implemented | No wager-specific command exists; confidence is captured within other flows only.【F:great_work/discord_bot.py†L32-L176】 |
| Provide the `/recruit` slash command. | Implemented | Recruitment attempts are exposed with validation and feedback.【F:great_work/discord_bot.py†L114-L142】 |
| Provide the `/launch_expedition` slash command. | Implemented | Expedition queuing is available through Discord with preparation inputs.【F:great_work/discord_bot.py†L59-L114】 |
| Provide the `/conference` slash command. | Not Implemented | No conference/symposium stance command has been added yet.【F:great_work/discord_bot.py†L32-L176】 |
| Provide the `/status` slash command. | Implemented | Players can retrieve reputation, influence, and cooldown information.【F:great_work/discord_bot.py†L142-L156】 |
| Provide the `/export_log` slash command. | Implemented | Recent events and press can be exported via Discord.【F:great_work/discord_bot.py†L156-L176】 |
| Provide an administrative hotfix command for real-time corrections. | Not Implemented | There are no admin-only commands or overrides available yet.【F:great_work/discord_bot.py†L32-L176】 |

### Data and Persistence

| Requirement | Status | Notes |
| --- | --- | --- |
| Implement a state manager backed by SQLite to store authoritative game data. | Implemented | `GameState` manages SQLite persistence for players, scholars, events, and press artefacts.【F:great_work/state.py†L18-L233】 |
| Maintain an append-only JSON event log. | Implemented | Events table records timestamped JSON payloads via `append_event`.【F:great_work/state.py†L24-L112】【F:great_work/service.py†L120-L440】 |
| Record players in the event log. | Not Implemented | Player creation/update persists to SQLite but does not emit corresponding event entries.【F:great_work/service.py†L98-L214】 |
| Record scholars in the event log. | Partially Implemented | Scholar spawning and retirement emit events, yet ongoing updates (mentorship, contracts) are not logged because the mechanics are absent.【F:great_work/service.py†L440-L518】 |
| Record theories in the event log. | Implemented | Theory submissions append structured events alongside press releases.【F:great_work/service.py†L120-L214】 |
| Record expeditions in the event log. | Implemented | Expedition launches and resolutions both write detailed events and persistence records.【F:great_work/service.py†L214-L383】 |
| Record factions in the event log. | Not Implemented | There is no dedicated event stream for faction standing changes beyond implicit influence adjustments.【F:great_work/service.py†L506-L566】 |
| Record relationships in the event log. | Partially Implemented | Relationship values update in SQLite, but only expedition outcomes append related events while other adjustments remain silent.【F:great_work/service.py†L383-L440】 |
| Record events in the event log. | Implemented | General gameplay actions (theories, expeditions, recruitment, defection) append timestamped events.【F:great_work/service.py†L120-L440】 |
| Record press releases in the event log. | Implemented | Press artefacts are archived via the `press_releases` table and exposed for export.【F:great_work/state.py†L112-L210】【F:great_work/service.py†L472-L506】 |
| Record contracts in the event log. | Not Implemented | Contract workflows are not yet built, leaving the offers table unused in practice.【F:great_work/state.py†L112-L210】 |
| Support exporting the event log for external review or backup. | Implemented | `/export_log` streams recent events and press via Discord using the persisted records.【F:great_work/service.py†L472-L506】【F:great_work/discord_bot.py†L156-L176】 |

### LLM-Driven Narrative

| Requirement | Status | Notes |
| --- | --- | --- |
| Integrate LLM personas to generate scholar reactions. | Not Implemented | Scholar reactions rely on templated catchphrases without LLM integration today.【F:great_work/service.py†L600-L633】 |
| Integrate LLM personas to generate press content. | Not Implemented | Press releases are template-driven with no external model calls.【F:great_work/press.py†L12-L128】 |
| Use deterministic prompts when invoking the LLM. | Not Implemented | No prompting system is present yet; deterministic RNG is only used for procedural text. |
| Cache persona snippets for reuse during generation. | Not Implemented | Persona cache mechanisms are absent alongside the missing LLM pipeline. |
| Constrain LLM outputs with templates. | Not Implemented | Templates exist but are not yet combined with model outputs to enforce structure.【F:great_work/press.py†L12-L128】 |
| Enforce character limits on LLM outputs to preserve tone and format. | Not Implemented | Output length control awaits the future LLM layer. |

### MVP Delivery

| Requirement | Status | Notes |
| --- | --- | --- |
| Deliver the first release within approximately two to four weeks. | Not Evaluated | Timeline tracking is outside the repository scope. |
| Include scholar generation in the MVP scope. | Implemented | Procedural scholar generation and seeding are in place via `ScholarRepository`.【F:great_work/scholars.py†L14-L116】 |
| Include reputation tracking in the MVP scope. | Implemented | Player reputation adjusts through wagers with configured bounds.【F:great_work/service.py†L286-L383】【F:great_work/config.py†L10-L53】 |
| Include influence tracking in the MVP scope. | Implemented | Influence storage, caps, and Discord visibility are live.【F:great_work/service.py†L506-L566】【F:great_work/discord_bot.py†L118-L150】 |
| Include expedition resolution in the MVP scope. | Implemented | Expedition queuing and resolving are functional with persistence and press.【F:great_work/service.py†L214-L383】 |
| Include Discord integration in the MVP scope. | Implemented | Multiple gameplay commands operate through Discord interactions.【F:great_work/discord_bot.py†L32-L176】 |
| Include a daily cron job in the MVP scope. | Implemented | `GazetteScheduler` leverages APScheduler to run daily digest jobs. 【F:great_work/scheduler.py†L12-L64】 |
| Include Gazette digest generation in the MVP scope. | Implemented | Digests run through `advance_digest` and expedition resolution, producing press artefacts.【F:great_work/scheduler.py†L34-L53】【F:great_work/service.py†L506-L633】 |
| Include press generation in the MVP scope. | Implemented | Press templates cover bulletins, manifestos, reports, gossip, recruitment, and defection items.【F:great_work/press.py†L12-L128】 |
| Include Symposium event hosting in the MVP scope. | Partially Implemented | A symposium heartbeat is scheduled, but full event mechanics remain to be built.【F:great_work/scheduler.py†L45-L64】 |
| Include event log export in the MVP scope. | Implemented | `/export_log` exposes recent events and press for review.【F:great_work/service.py†L472-L506】【F:great_work/discord_bot.py†L156-L176】 |
| Include admin hotfix functionality in the MVP scope. | Not Implemented | No admin commands or overrides are available yet.【F:great_work/discord_bot.py†L32-L176】 |
| Defer implementation of Great Projects beyond the MVP. | Not Implemented | Great Projects are already available as an expedition option rather than deferred.【F:great_work/service.py†L214-L383】 |

## Non-Functional Requirements

### Target Audience and Scale

| Requirement | Status | Notes |
| --- | --- | --- |
| Optimize pacing for small friend groups. | Partially Implemented | Twice-daily digest scheduling and follow-up processing support slower pacing, though symposium participation loops are still pending.【F:great_work/scheduler.py†L12-L64】【F:great_work/service.py†L506-L633】 |
| Optimize complexity for small friend groups. | Not Evaluated | No instrumentation or documentation addresses cognitive load or scaling complexity yet. |
| Ensure systems remain manageable at the intended small-group scale. | Partially Implemented | Current mechanics and persistence target a single Discord server, but tooling for moderation or scaling beyond core commands is absent.【F:great_work/discord_bot.py†L32-L176】 |

### Narrative Tone and Consistency

| Requirement | Status | Notes |
| --- | --- | --- |
| Keep all narrative outputs public to every participant. | Partially Implemented | Press artefacts are archived, yet automated publication to shared channels is still missing.【F:great_work/service.py†L120-L633】【F:great_work/scheduler.py†L12-L64】 |
| Enforce template usage for generated text. | Implemented | All press copy is generated through structured templates with deterministic placeholders.【F:great_work/press.py†L12-L128】 |
| Align generated text with persona sheets to preserve tone continuity. | Not Implemented | LLM-driven persona prompts and alignment checks have not been built.【F:docs/HLD.md†L318-L369】【F:great_work/service.py†L600-L633】 |

### Pacing and Engagement

| Requirement | Status | Notes |
| --- | --- | --- |
| Maintain a twice-daily cadence for Gazette digests. | Partially Implemented | Scheduler jobs trigger at configured times, though publishing requires a custom publisher hook.【F:great_work/scheduler.py†L12-L53】 |
| Schedule weekly Symposium events to drive communal discussion. | Partially Implemented | A weekly heartbeat exists, but it lacks topics, participation tracking, or consequences.【F:great_work/scheduler.py†L45-L64】 |
| Support idle-friendly scheduling to avoid overwhelming players. | Partially Implemented | Asynchronous Discord commands and digest gating help pacing, yet mentorship and symposium mechanics may add additional load once implemented.【F:great_work/discord_bot.py†L32-L176】【F:great_work/service.py†L506-L633】 |

### Reproducibility and Auditability

| Requirement | Status | Notes |
| --- | --- | --- |
| Provide deterministic seeding for procedural content generation systems. | Implemented | Procedural content leverages a deterministic RNG and seeded scholar repository to ensure repeatable outputs.【F:great_work/rng.py†L1-L63】【F:great_work/scholars.py†L14-L116】 |
| Offer a fixed RNG mode to support replay scenarios. | Implemented | `DeterministicRNG` seeded within `GameService` enables deterministic resolution paths for replays.【F:great_work/service.py†L80-L214】【F:great_work/rng.py†L1-L63】 |
| Offer a fixed RNG mode to support audit scenarios. | Implemented | The same deterministic RNG underpins audits by reproducing rolls from stored inputs.【F:great_work/service.py†L80-L214】【F:great_work/expeditions.py†L38-L86】 |
| Retain complete event logs so that game state can be reconstructed after the fact. | Implemented | Events, press, scholars, and expeditions persist in SQLite and can be exported for audit.【F:great_work/state.py†L18-L233】【F:great_work/service.py†L472-L506】 |

### Cost and Operational Control

| Requirement | Status | Notes |
| --- | --- | --- |
| Minimize LLM generation costs by batching reactions. | Not Implemented | No LLM integration exists, so batching controls are absent.【F:great_work/press.py†L12-L128】 |
| Limit LLM outputs to concise, single-line reactions when possible. | Not Implemented | Template output is static; there are no runtime constraints for future model text.【F:great_work/press.py†L12-L128】 |
| Restrict posting frequency to control operational expenses. | Partially Implemented | Scheduled digests limit automated posts, but ad hoc command usage still posts immediately without rate controls.【F:great_work/scheduler.py†L12-L64】【F:great_work/discord_bot.py†L32-L176】 |
| Run a daily cron process to execute scheduled maintenance tasks. | Implemented | APScheduler-backed digests and symposium heartbeat provide daily and weekly automation.【F:great_work/scheduler.py†L12-L64】 |

### Licensing and Safety

| Requirement | Status | Notes |
| --- | --- | --- |
| Release source code under the MIT license. | Implemented | The repository ships with an MIT license covering the codebase.【F:LICENSE†L1-L21】 |
| Release source code under the MPL-2.0 license when applicable. | Not Implemented | No MPL licensing information is included in the repository.【F:LICENSE†L1-L21】 |
| Publish narrative assets under the CC BY-SA 4.0 license. | Not Implemented | Asset licensing for narrative content is unspecified in documentation or headers. |
| Apply a blocklist to generated text. | Not Implemented | There are no moderation or filtering hooks for generated copy yet.【F:great_work/press.py†L12-L128】 |
| Subject risky generated outputs to manual review. | Not Implemented | Manual review workflows are not present without the LLM pipeline.【F:great_work/service.py†L600-L633】 |

### Success Criteria and Iteration

| Requirement | Status | Notes |
| --- | --- | --- |
| Measure success through the emergence of scholar nicknames. | Not Implemented | No telemetry or analytics track nickname creation or usage. |
| Measure success through the sharing of press releases by players. | Not Implemented | Sharing metrics are not gathered or reported. |
| Measure success through the creation of player manifestos. | Not Implemented | Manifesto tracking is not implemented in code or persistence. |
| Adjust mechanics iteratively if playtests miss success targets. | Not Evaluated | Iteration process depends on external playtesting and is not represented in the repository. |

### Open-Source Readiness

| Requirement | Status | Notes |
| --- | --- | --- |
| Provide structured YAML assets to support community contributions. | Implemented | Scholar templates, name banks, and settings live in YAML files for easy extension.【F:great_work/data/scholars_base.yaml†L1-L176】【F:great_work/data/settings.yaml†L1-L23】 |
| Supply deterministic tooling to support community contributions. | Implemented | Deterministic RNG utilities ensure contributors can reproduce outcomes.【F:great_work/rng.py†L1-L63】 |
| Supply administrative utilities that help moderators maintain tonal alignment. | Not Implemented | No admin tooling or moderation aids exist yet.【F:great_work/discord_bot.py†L32-L176】 |
| Keep the codebase accessible to facilitate forking. | Implemented | MIT licensing and modular Python packages keep the project approachable for forks.【F:LICENSE†L1-L21】【F:great_work/__init__.py†L1-L7】 |
| Document the codebase to facilitate forking. | Partially Implemented | High-level design and planning documents exist, but API-level documentation remains limited.【F:docs/HLD.md†L1-L386】【F:docs/implementation_plan.md†L1-L60】 |

### Accessibility of Records

| Requirement | Status | Notes |
| --- | --- | --- |
| Ensure every action remains permanently accessible. | Partially Implemented | Press and events persist in SQLite, yet automated public surfacing is still pending.【F:great_work/state.py†L18-L233】【F:great_work/scheduler.py†L12-L64】 |
| Ensure every action remains publicly citable. | Partially Implemented | Archived press can be exported, but no public-facing archive or permalink system exists yet.【F:great_work/service.py†L472-L506】【F:great_work/discord_bot.py†L142-L176】 |
| Offer exportable logs for sharing game records with external audiences. | Implemented | `/export_log` and press archive helpers provide exportable records.【F:great_work/service.py†L472-L506】【F:great_work/discord_bot.py†L156-L176】 |
| Offer exportable logs for sharing game records with auditors. | Implemented | The same export tooling supports audit needs with deterministic state reconstruction.【F:great_work/service.py†L472-L506】【F:great_work/state.py†L18-L233】 |
