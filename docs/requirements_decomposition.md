# Requirement Decomposition

## Functional Requirements

### Core Gameplay Loop and Transparency

| Requirement | Status | Notes |
| --- | --- | --- |
| Provide an asynchronous multiplayer experience supporting between four and eight concurrent players. | Partially Implemented | Discord slash commands let multiple players act asynchronously, but there is no explicit enforcement of player counts or turn management yet.【F:great_work/discord_bot.py†L76-L324】 |
| Deliver all player moves through a Discord bot. | Partially Implemented | Core actions (theories, expeditions, recruitment, status, archives) are exposed via slash commands, while defection handling and admin moves remain service-only.【F:great_work/discord_bot.py†L114-L324】【F:great_work/service.py†L394-L466】 |
| Make every action publicly visible to all participants. | Partially Implemented | Core orders and Gazette updates post to their dedicated Discord channels, though some utility commands still reply ephemerally and symposium beats remain undeveloped.【F:great_work/discord_bot.py†L114-L314】【F:great_work/scheduler.py†L20-L59】 |
| Advance the shared narrative timeline by one in-game year for each real-world day that passes. | Implemented | Digest advancement calls into timeline persistence to convert elapsed real days into in-world years, emitting Gazette updates whenever the calendar rolls forward.【F:great_work/service.py†L515-L553】【F:great_work/state.py†L322-L346】 |

### Scholar Management

| Requirement | Status | Notes |
| --- | --- | --- |
| Maintain a persistent roster of 20 to 30 scholars. | Implemented | `GameService` enforces minimum and maximum roster sizes, spawning or retiring scholars as needed during digest advancement.【F:great_work/service.py†L581-L616】 |
| Track memories, personalities, and interrelationships for each scholar. | Implemented | Scholar models persist memory facts, feelings, scars, and relationships through SQLite tables and helper methods.【F:great_work/models.py†L23-L119】【F:great_work/state.py†L200-L243】 |
| Support handcrafted scholars alongside procedurally generated scholars. | Implemented | The repository loads authored templates and deterministically generates new scholars when filling the roster or spawning sidecasts.【F:great_work/scholars.py†L18-L140】 |
| Enable scholars to emerge through defined lifecycle events. | Implemented | Successful expeditions can spawn sidecast scholars who join the roster with recorded press.【F:great_work/service.py†L728-L759】 |
| Allow scholars to receive mentorship from other scholars or players. | Not Implemented | No mentorship or assignment commands exist yet; digest advancement only progresses automatic career ticks without player intervention.【F:great_work/service.py†L617-L686】 |
| Evaluate defection and return events for scholars using probabilistic logic. | Partially Implemented | Defection probability and event logging are implemented, but return arcs and chained offers are still limited to simple follow-up gossip.【F:great_work/scholars.py†L162-L175】【F:great_work/service.py†L394-L466】【F:great_work/service.py†L650-L686】 |

### Confidence Wagering

| Requirement | Status | Notes |
| --- | --- | --- |
| Require players to declare confidence levels before resolving an action. | Implemented | Theory submissions and expeditions demand explicit `ConfidenceLevel` selections, aligning with the wager system.【F:great_work/service.py†L125-L214】【F:great_work/discord_bot.py†L114-L206】 |
| Deduct reputation stakes that scale with the declared confidence level. | Implemented | Outcome resolution applies the configured wager table and clamps reputation within bounds.【F:great_work/service.py†L214-L318】【F:great_work/config.py†L11-L41】 |
| Apply a cooldown penalty to any player who declares a high-stakes wager. | Implemented | Staking a career enforces recruitment cooldowns that decay during digests and influence recruitment odds.【F:great_work/service.py†L214-L318】【F:great_work/service.py†L689-L695】 |

### Expeditions and Outcomes

| Requirement | Status | Notes |
| --- | --- | --- |
| Offer think tank expeditions as a selectable option. | Implemented | Discord commands and service logic accept `think_tank` expeditions with tailored costs and rewards.【F:great_work/discord_bot.py†L142-L206】【F:great_work/service.py†L170-L214】 |
| Offer field expeditions as a selectable option. | Implemented | Field expeditions are handled alongside other types using the same queue and resolver flow.【F:great_work/service.py†L170-L318】 |
| Offer Great Projects as a selectable option. | Implemented | The resolver and cost tables include `great_project` with full implementation.【F:great_work/service.py†L170-L318】【F:great_work/expeditions.py†L60-L116】 |
| Resolve expedition outcomes using a d100 recipe. | Implemented | `ExpeditionResolver` rolls d100 and computes modifiers before determining outcomes.【F:great_work/expeditions.py†L60-L101】 |
| Incorporate preparation modifiers into expedition resolution. | Implemented | Preparation inputs contribute to the modifier sum applied during resolution.【F:great_work/models.py†L122-L135】【F:great_work/expeditions.py†L60-L75】 |
| Incorporate expertise modifiers into expedition resolution. | Implemented | Expertise bonuses are part of the `ExpeditionPreparation` data used in modifier calculations.【F:great_work/models.py†L122-L135】 |
| Incorporate friction modifiers into expedition resolution. | Implemented | Site and political friction values are included in the aggregated modifier.【F:great_work/models.py†L122-L135】 |
| Define success bands for expedition results. | Implemented | Resolver thresholds map final scores to failure, partial, success, and landmark bands.【F:great_work/expeditions.py†L72-L116】 |
| Define failure bands for expedition results. | Implemented | Failure tables provide typed outcomes per expedition and depth when rolls fall below success thresholds.【F:great_work/expeditions.py†L72-L92】【F:great_work/data/failure_tables.yaml†L1-L44】 |
| Scale failure consequence tables based on the depth of pre-expedition preparation. | Implemented | Separate shallow/deep tables and sideways discovery entries are selected by depth.【F:great_work/data/failure_tables.yaml†L1-L44】 |

### Influence Economy

| Requirement | Status | Notes |
| --- | --- | --- |
| Track each player's influence as a five-dimensional faction vector. | Implemented | Player records persist influence by faction in SQLite and expose it via status commands.【F:great_work/state.py†L136-L170】【F:great_work/discord_bot.py†L236-L253】 |
| Tie the soft cap for each influence dimension to the player's reputation score. | Implemented | Influence adjustments clamp against a cap derived from reputation-driven settings.【F:great_work/service.py†L677-L772】【F:great_work/config.py†L11-L41】 |
| Prevent players from monopolizing a single faction by enforcing soft caps. | Implemented | `_apply_influence_change` enforces the computed cap when adding influence, limiting single-faction hoarding.【F:great_work/service.py†L785-L793】 |

### Press Artifacts and Gazette Cadence

| Requirement | Status | Notes |
| --- | --- | --- |
| Auto-generate a bulletin for every recorded action. | Partially Implemented | Theory submissions and key events generate press, but not every event (e.g., admin actions) has a dedicated bulletin yet.【F:great_work/service.py†L125-L686】 |
| Auto-generate a manifest for every recorded action. | Partially Implemented | Expedition launches create research manifestos, though other action types reuse different templates or none at all.【F:great_work/service.py†L170-L318】【F:great_work/press.py†L20-L48】 |
| Auto-generate a report for every recorded action. | Partially Implemented | Expedition resolutions produce discovery or retraction reports, but other gameplay actions may only log events without reports.【F:great_work/service.py†L226-L392】【F:great_work/press.py†L61-L145】 |
| Auto-generate a gossip item for every recorded action. | Partially Implemented | Recruitment, follow-ups, and promotions emit gossip, yet numerous actions remain gossip-free today.【F:great_work/service.py†L320-L686】【F:great_work/press.py†L100-L145】 |
| Publish Gazette digests twice per real day summarizing actions. | Implemented | Scheduled digests now publish to the configured Gazette channel automatically while processing queued orders through `advance_digest`.【F:great_work/scheduler.py†L30-L58】【F:great_work/discord_bot.py†L91-L109】 |
| Host weekly Symposium threads to highlight notable developments. | Partially Implemented | A scheduled symposium heartbeat exists, but no topic selection or participation mechanics are implemented.【F:great_work/scheduler.py†L32-L52】 |

### Discord UX and Commands

| Requirement | Status | Notes |
| --- | --- | --- |
| Expose gameplay interactions through the `#orders` channel. | Implemented | Orders, recruitment, and digest resolutions mirror their announcements into the configured orders channel automatically.【F:great_work/discord_bot.py†L138-L234】 |
| Expose gameplay interactions through the `#gazette` channel. | Implemented | Gazette digests publish press copy to the configured Gazette channel whenever the scheduler runs.【F:great_work/discord_bot.py†L89-L113】【F:great_work/scheduler.py†L20-L59】 |
| Expose gameplay interactions through the `#table-talk` channel. | Implemented | Players can send moderated chatter to the table-talk channel via the `/table_talk` command.【F:great_work/discord_bot.py†L289-L314】 |
| Provide the `/submit_theory` slash command. | Implemented | Command registered and wired to `GameService.submit_theory`.【F:great_work/discord_bot.py†L114-L140】 |
| Provide the `/wager` slash command. | Implemented | Discord exposes a dedicated `/wager` command that surfaces wager payouts, thresholds, and bounds from the service layer.【F:great_work/discord_bot.py†L256-L272】【F:great_work/service.py†L486-L505】 |
| Provide the `/recruit` slash command. | Implemented | Recruitment attempts are exposed through Discord and backed by `GameService.attempt_recruitment`.【F:great_work/discord_bot.py†L209-L234】【F:great_work/service.py†L320-L392】 |
| Provide the `/expedition` slash command. | Implemented | Expedition launch and resolution commands integrate with the service queue and resolver.【F:great_work/discord_bot.py†L142-L206】【F:great_work/service.py†L170-L318】 |
| Provide the `/status` slash command. | Implemented | Status embeds return reputation, influence, caps, cooldowns, and action thresholds drawn from `GameService.player_status`.【F:great_work/discord_bot.py†L236-L255】【F:great_work/service.py†L468-L505】 |
| Provide the `/gazette` slash command. | Implemented | Gazette browsing pulls from the stored press archive.【F:great_work/discord_bot.py†L274-L287】【F:great_work/state.py†L404-L417】 |
| Provide the `/export_log` slash command. | Implemented | Recent events and press releases can be exported directly from Discord.【F:great_work/discord_bot.py†L289-L301】【F:great_work/service.py†L486-L513】 |

## Non-Functional Requirements

### Target Audience and Scale

| Requirement | Status | Notes |
| --- | --- | --- |
| Optimize pacing for small friend groups. | Partially Implemented | Twice-daily digest scheduling and follow-up processing support slower pacing, though symposium participation loops are still pending.【F:great_work/scheduler.py†L20-L59】【F:great_work/service.py†L515-L686】 |
| Optimize complexity for small friend groups. | Not Evaluated | No instrumentation or documentation addresses cognitive load or scaling complexity yet. |
| Ensure systems remain manageable at the intended small-group scale. | Partially Implemented | Current mechanics and persistence target a single Discord server, but tooling for moderation or scaling beyond core commands is absent.【F:great_work/discord_bot.py†L76-L324】 |

### Narrative Tone and Consistency

| Requirement | Status | Notes |
| --- | --- | --- |
| Keep all narrative outputs public to every participant. | Partially Implemented | Press artefacts are archived, yet automated publication to shared channels is still missing.【F:great_work/service.py†L125-L686】【F:great_work/scheduler.py†L20-L59】 |
| Enforce template usage for generated text. | Implemented | All press copy is generated through structured templates with deterministic placeholders.【F:great_work/press.py†L20-L155】 |
| Align generated text with persona sheets to preserve tone continuity. | Not Implemented | LLM-driven persona prompts and alignment checks have not been built.【F:docs/HLD.md†L318-L369】【F:great_work/press.py†L20-L155】 |

### Pacing and Engagement

| Requirement | Status | Notes |
| --- | --- | --- |
| Maintain a twice-daily cadence for Gazette digests. | Implemented | Scheduler jobs trigger at configured times and automatically publish Gazette digests to the designated channel.【F:great_work/scheduler.py†L30-L58】【F:great_work/discord_bot.py†L91-L109】 |
| Schedule weekly Symposium events to drive communal discussion. | Partially Implemented | A weekly heartbeat exists, but it lacks topics, participation tracking, or consequences.【F:great_work/scheduler.py†L32-L52】 |
| Support idle-friendly scheduling to avoid overwhelming players. | Partially Implemented | Asynchronous Discord commands and digest gating help pacing, yet mentorship and symposium mechanics may add additional load once implemented.【F:great_work/discord_bot.py†L76-L324】【F:great_work/service.py†L515-L686】 |

### Reproducibility and Auditability

| Requirement | Status | Notes |
| --- | --- | --- |
| Provide deterministic seeding for procedural content generation systems. | Implemented | Procedural content leverages a deterministic RNG and seeded scholar repository to ensure repeatable outputs.【F:great_work/rng.py†L1-L63】【F:great_work/scholars.py†L18-L140】 |
| Offer a fixed RNG mode to support replay scenarios. | Implemented | `DeterministicRNG` seeded within `GameService` enables deterministic resolution paths for replays.【F:great_work/service.py†L86-L214】【F:great_work/rng.py†L1-L63】 |
| Offer a fixed RNG mode to support audit scenarios. | Implemented | The same deterministic RNG underpins audits by reproducing rolls from stored inputs.【F:great_work/service.py†L170-L318】【F:great_work/expeditions.py†L60-L116】 |
| Retain complete event logs so that game state can be reconstructed after the fact. | Implemented | Events, press, scholars, and expeditions persist in SQLite and can be exported for audit.【F:great_work/state.py†L200-L417】【F:great_work/service.py†L486-L513】 |

### Cost and Operational Control

| Requirement | Status | Notes |
| --- | --- | --- |
| Minimize LLM generation costs by batching reactions. | Not Implemented | No LLM integration exists, so batching controls are absent.【F:great_work/press.py†L20-L155】 |
| Limit LLM outputs to concise, single-line reactions when possible. | Not Implemented | Template output is static; there are no runtime constraints for future model text.【F:great_work/press.py†L20-L155】 |
| Restrict posting frequency to control operational expenses. | Partially Implemented | Scheduled digests limit automated posts, but ad hoc command usage still posts immediately without rate controls.【F:great_work/scheduler.py†L20-L59】【F:great_work/discord_bot.py†L76-L324】 |
| Run a daily cron process to execute scheduled maintenance tasks. | Implemented | APScheduler-backed digests and symposium heartbeat provide daily and weekly automation.【F:great_work/scheduler.py†L30-L58】 |

### Licensing and Safety

| Requirement | Status | Notes |
| --- | --- | --- |
| Release source code under the MIT license. | Implemented | The repository ships with an MIT license covering the codebase.【F:LICENSE†L1-L21】 |
| Release source code under the MPL-2.0 license when applicable. | Not Implemented | No MPL licensing information is included in the repository.【F:LICENSE†L1-L21】 |
| Publish narrative assets under the CC BY-SA 4.0 license. | Not Implemented | Asset licensing for narrative content is unspecified in documentation or headers. |
| Apply a blocklist to generated text. | Not Implemented | There are no moderation or filtering hooks for generated copy yet.【F:great_work/press.py†L20-L155】 |
| Subject risky generated outputs to manual review. | Not Implemented | Manual review workflows are not present without the LLM pipeline.【F:great_work/service.py†L394-L466】【F:great_work/press.py†L20-L145】 |

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
| Supply administrative utilities that help moderators maintain tonal alignment. | Not Implemented | No admin tooling or moderation aids exist yet.【F:great_work/discord_bot.py†L76-L324】 |
| Keep the codebase accessible to facilitate forking. | Implemented | MIT licensing and modular Python packages keep the project approachable for forks.【F:LICENSE†L1-L21】【F:great_work/__init__.py†L1-L7】 |
| Document the codebase to facilitate forking. | Partially Implemented | High-level design and planning documents exist, but API-level documentation remains limited.【F:docs/HLD.md†L1-L386】【F:docs/implementation_plan.md†L1-L78】 |

### Accessibility of Records

| Requirement | Status | Notes |
| --- | --- | --- |
| Ensure every action remains permanently accessible. | Partially Implemented | Press and events persist in SQLite, yet automated public surfacing is still pending.【F:great_work/state.py†L200-L417】【F:great_work/scheduler.py†L20-L48】 |
| Ensure every action remains publicly citable. | Partially Implemented | Archived press can be exported, but no public-facing archive or permalink system exists yet.【F:great_work/service.py†L486-L513】【F:great_work/discord_bot.py†L274-L301】 |
| Offer exportable logs for sharing game records with external audiences. | Implemented | `/export_log` and press archive helpers provide exportable records.【F:great_work/service.py†L486-L513】【F:great_work/discord_bot.py†L289-L301】 |
| Offer exportable logs for sharing game records with auditors. | Implemented | The same export tooling supports audit needs with deterministic state reconstruction.【F:great_work/service.py†L486-L513】【F:great_work/state.py†L200-L417】 |
