# Requirement Decomposition

## Functional Requirements

### Core Gameplay Loop and Transparency
- Provide an asynchronous multiplayer experience supporting between four and eight concurrent players.
- Deliver all player moves through a Discord bot.
- Make every action publicly visible to all participants.
- Advance the shared narrative timeline by one in-game year for each real-world day that passes.

### Scholar Management
- Maintain a persistent roster of 20 to 30 scholars.
- Track memories, personalities, and interrelationships for each scholar.
- Support handcrafted scholars alongside procedurally generated scholars.
- Enable scholars to emerge through defined lifecycle events.
- Allow scholars to receive mentorship from other scholars or players.
- Evaluate defection and return events for scholars using probabilistic logic.

### Confidence Wagering
- Require players to declare confidence levels before resolving an action.
- Deduct reputation stakes that scale with the declared confidence level.
- Apply a cooldown penalty to any player who declares a high-stakes wager.

### Expeditions and Outcomes
- Offer think tank expeditions as a selectable option.
- Offer field expeditions as a selectable option.
- Offer deferred Great Projects as a selectable option.
- Resolve expedition outcomes using a d100 recipe.
- Incorporate preparation modifiers into expedition resolution.
- Incorporate expertise modifiers into expedition resolution.
- Incorporate friction modifiers into expedition resolution.
- Define success bands for expedition results.
- Define failure bands for expedition results.
- Scale failure consequence tables based on the depth of pre-expedition preparation.

### Influence Economy
- Track each player's influence as a five-dimensional faction vector.
- Tie the soft cap for each influence dimension to the player's reputation score.
- Prevent players from monopolizing a single faction by enforcing soft caps.

### Press Artifacts and Gazette Cadence
- Auto-generate a bulletin for every recorded action.
- Auto-generate a manifest for every recorded action.
- Auto-generate a report for every recorded action.
- Auto-generate a gossip item for every recorded action.
- Publish Gazette digests twice per real day summarizing actions.
- Host weekly Symposium threads to highlight notable developments.

### Discord UX and Commands
- Expose gameplay interactions through the `#orders` channel.
- Expose gameplay interactions through the `#gazette` channel.
- Expose gameplay interactions through the `#table-talk` channel.
- Provide the `/submit_theory` slash command.
- Provide the `/wager` slash command.
- Provide the `/recruit` slash command.
- Provide the `/launch_expedition` slash command.
- Provide the `/conference` slash command.
- Provide the `/status` slash command.
- Provide the `/export_log` slash command.
- Provide an administrative hotfix command for real-time corrections.

### Data and Persistence
- Implement a state manager backed by SQLite to store authoritative game data.
- Maintain an append-only JSON event log.
- Record players in the event log.
- Record scholars in the event log.
- Record theories in the event log.
- Record expeditions in the event log.
- Record factions in the event log.
- Record relationships in the event log.
- Record events in the event log.
- Record press releases in the event log.
- Record contracts in the event log.
- Support exporting the event log for external review or backup.

### LLM-Driven Narrative
- Integrate LLM personas to generate scholar reactions.
- Integrate LLM personas to generate press content.
- Use deterministic prompts when invoking the LLM.
- Cache persona snippets for reuse during generation.
- Constrain LLM outputs with templates.
- Enforce character limits on LLM outputs to preserve tone and format.

### MVP Delivery
- Deliver the first release within approximately two to four weeks.
- Limit the MVP implementation to roughly 2,000 lines of Python.
- Include scholar generation in the MVP scope.
- Include reputation tracking in the MVP scope.
- Include influence tracking in the MVP scope.
- Include expedition resolution in the MVP scope.
- Include Discord integration in the MVP scope.
- Include a daily cron job in the MVP scope.
- Include Gazette digest generation in the MVP scope.
- Include press generation in the MVP scope.
- Include Symposium event hosting in the MVP scope.
- Include event log export in the MVP scope.
- Include admin hotfix functionality in the MVP scope.
- Defer implementation of Great Projects beyond the MVP.

## Non-Functional Requirements

### Target Audience and Scale
- Optimize pacing for small friend groups.
- Optimize complexity for small friend groups.
- Ensure systems remain manageable at the intended small-group scale.

### Narrative Tone and Consistency
- Keep all narrative outputs public to every participant.
- Enforce template usage for generated text.
- Align generated text with persona sheets to preserve tone continuity.

### Pacing and Engagement
- Maintain a twice-daily cadence for Gazette digests.
- Schedule weekly Symposium events to drive communal discussion.
- Support idle-friendly scheduling to avoid overwhelming players.

### Reproducibility and Auditability
- Provide deterministic seeding for procedural content generation systems.
- Offer a fixed RNG mode to support replay scenarios.
- Offer a fixed RNG mode to support audit scenarios.
- Retain complete event logs so that game state can be reconstructed after the fact.

### Cost and Operational Control
- Minimize LLM generation costs by batching reactions.
- Limit LLM outputs to concise, single-line reactions when possible.
- Restrict posting frequency to control operational expenses.
- Run a daily cron process to execute scheduled maintenance tasks.

### Licensing and Safety
- Release source code under the MIT license.
- Release source code under the MPL-2.0 license when applicable.
- Publish narrative assets under the CC BY-SA 4.0 license.
- Apply a blocklist to generated text.
- Subject risky generated outputs to manual review.

### Success Criteria and Iteration
- Measure success through the emergence of scholar nicknames.
- Measure success through the sharing of press releases by players.
- Measure success through the creation of player manifestos.
- Adjust mechanics iteratively if playtests miss success targets.

### Open-Source Readiness
- Provide structured YAML assets to support community contributions.
- Supply deterministic tooling to support community contributions.
- Supply administrative utilities that help moderators maintain tonal alignment.
- Keep the codebase accessible to facilitate forking.
- Document the codebase to facilitate forking.

### Accessibility of Records
- Ensure every action remains permanently accessible.
- Ensure every action remains publicly citable.
- Offer exportable logs for sharing game records with external audiences.
- Offer exportable logs for sharing game records with auditors.
