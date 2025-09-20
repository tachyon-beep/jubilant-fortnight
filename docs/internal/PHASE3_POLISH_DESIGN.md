# Phase 3 Polish Design Brief

## Purpose & Scope

Phase 3 focuses on operational polish: actionable telemetry, resilient archive publishing, and richer multi-layer press cadence. This brief captures the target outcomes, proposed approaches, and open decisions so implementation can proceed without ambiguity. It drills into three workstreams that remain after the latest telemetry/dispatcher audit and flags where stakeholder input is needed before coding.

## 1. Telemetry Dashboards & Success Metrics

### Current State
- All slash commands flow through `track_command`, emitting command usage with player, guild, channel, duration, and success tags (`great_work/telemetry_decorator.py:12`).
- LLM activity, system pause/resume events, queue-depth sampling, symposium scoring/debt telemetry, and player-state snapshots are recorded in `telemetry.db` and surfaced via `/telemetry_report` and the FastAPI dashboard (`great_work/telemetry.py:520`, `great_work/telemetry.py:788`, `ops/telemetry-dashboard/app.py:1`).
- Requirements still call for engagement funnels and explicit success criteria tracking (`docs/requirements_evaluation.md:157`).

### Objectives
1. Provide on-demand dashboards (Discord command + bundled HTML dashboard) covering:
   - Layered press production and release cadence (by type, scheduled vs immediate).
   - Engagement metrics: unique players per digest, symposium participation, table-talk volume.
   - Symposium backlog health: proposal scoring weights, outstanding debt totals, reprisal counts.
   - Health signals: digest duration, LLM latency distribution, pause frequency.
2. Define success metrics aligned with product goals (e.g., % public vs ephemeral replies, avg time from press schedule to release).
3. Establish alert thresholds for pause duration, command error spikes, and archive export failures
   (defaults now recorded in the deployment guide).

### Proposed Approach
- **Schema additions:**
  - Queue depth snapshots are emitted directly via `track_queue_depth`; continue enriching layered press counts (ingest from `press_scheduled` events and scheduled queue releases).
  - Record digest runtime via a `track_performance` call wrapping `advance_digest` and `resolve_pending_expeditions`.
- **Reporting surfaces:**
  - Extend `/telemetry_report` with new sections (layered press, engagement, digest health, symposium scoring/debt) and paginate when output exceeds Discord limits.
  - Ship a lightweight FastAPI/Jinja dashboard inside the ops container to visualise historical metrics directly from `telemetry.db`, including symposium scoring tables, debt snapshots, and reprisal logs.
- **Alerting:**
  - Configurable thresholds exposed via environment variables (`GREAT_WORK_ALERT_MAX_DIGEST_MS`,
    `GREAT_WORK_ALERT_MAX_QUEUE`, `GREAT_WORK_ALERT_MIN_RELEASES`,
    `GREAT_WORK_ALERT_MAX_LLM_LATENCY_MS`, `GREAT_WORK_ALERT_LLM_FAILURE_RATE`,
    `GREAT_WORK_ALERT_MAX_ORDER_PENDING`, `GREAT_WORK_ALERT_MAX_ORDER_AGE_HOURS`). When breached,
    enqueue admin notifications, log system events, and surface a health summary in `/telemetry_report`.
- **Operator notes:**
  - `/telemetry_report` now prints queue depth averages/maxima alongside the active thresholds, giving moderators a quick read on backlog health.
  - Queue depth snapshots are sampled when upcoming highlights are generated (default horizon 48h); adjust horizon via `GREAT_WORK_CHANNEL_UPCOMING` settings if cadence changes.
  - Symposium sections list the highest-scored proposals (player, score, age) plus outstanding debt holders and any reprisals in the past 24 hours. Runbook:
    1. If backlog scoring is dominated by one player for multiple cycles, review scoring weights (/symposium_backlog) and consider manual curation.
    2. When a player’s debt exceeds the reprisal threshold for more than one digest, confirm a reprisal fired and ping moderators to nudge repayment.
    3. Three or more reprisals in a 24h window should prompt a moderation follow-up and potentially manual influence adjustments.
  - `/symposium_backlog` mirrors the dashboard ranking for ad-hoc Discord checks.
  - Symposium debt reprisals now schedule `symposium_reprimand` follow-ups that publish public warnings and appear in the dispatcher queue; review them via `/gw_admin list_orders` and cancel as needed with `/gw_admin cancel_order`.

### Decision Points
1. **Dashboard medium:** ✅ Use Discord `/telemetry_report` plus the bundled FastAPI/Jinja dashboard container for richer historical slices.
2. **Success metric targets:** Need product input on target ranges (e.g., acceptable pause duration, desired engagement numbers) before hard-coding alerts.

### Implementation Plan
1. **Done:** Instrument digest runtimes and layered press metrics (queue depth, scheduled release counts) in telemetry and surface them via `/telemetry_report`.
2. **Next:** Expose the aggregates to the FastAPI dashboard container and finalise success KPI targets with product.
3. Introduce alert evaluation during command execution (error rate thresholds) and document escalation workflows.
4. Document the workflow in `docs/implementation_plan.md` and operator guides.

## 2. Archive Automation & Hosting

### Current State
- Gazette scheduler exports the static archive every digest, syncs the contents into `web_archive_public/`, and uploads ZIP snapshots to the admin channel (`great_work/scheduler.py:20`, `docs/internal/ARCHIVE_OPERATIONS.md`).
- Hosting is handled by the bundled nginx container; optional managed adapters (S3/GitHub Pages) remain future work.

### Objectives
1. Publish the archive to a persistent host (S3 bucket, GitHub Pages, or similar) after each digest.
2. Implement retention policies for local and remote snapshots (e.g., keep last 30, prune older).
3. Provide a one-command operator workflow, with failure telemetry and admin alerts when publishing stalls.

- **Hosting target (decided):** Self-hosted static site served from the project’s container image so anyone can run the publisher container. The digest job publishes into the container volume and the container exposes the archive over HTTPS. (Alternatives such as S3/GitHub Pages remain viable if operators prefer managed hosting.)
- **Automation flow:**
  1. After archive export, sync `web_archive/` into `web_archive_public/` (served by the container volume).
  2. Record deployment metadata (digest timestamp) in telemetry via `track_system_event` and alert on failure.
  3. Zip snapshots remain for disaster recovery; prune older than retention window automatically.
- **Configuration:**
  - Extend settings with `archive.hosting` block (provider, credentials/env vars, retention days).
  - Add optional dry-run mode for local testing.
- **Monitoring:**
  - Emit telemetry on deployment duration/success.
  - Notify admin channel if publishing fails, including error summary and retry guidance.

### Decision Points
1. **Hosting provider choice:** ✅ Use the self-hosted containerized static server; publish pipeline writes to its mounted volume. Additional providers can be added later via adapters.
2. **Credential management:** Simplified—container runs with local filesystem access; no external credentials required unless operators add optional adapters.

### Implementation Plan
1. Prototype provider adapters (`archive.publishers.s3`, `archive.publishers.github_pages`) behind a common interface.
2. Wire `GazetteScheduler._publish_digest` to invoke the configured publisher after local export.
3. Implement snapshot pruning routine (local + remote) respecting retention config.
4. Capture deployment telemetry and admin notifications on failure.
5. Update `docs/internal/ARCHIVE_OPERATIONS.md`, README deployment section, and requirements tracking.

## 3. Mentorship/Admin Multi-layer Cadence

### Current State
- Expeditions, defections, symposiums, and admin notices use `MultiPressGenerator` to schedule layered follow-ups and delayed gossip (`great_work/service.py:595`, `great_work/multi_press.py:86`).
- Mentorship activations/completions and routine admin maintenance still emit single gossip artefacts without staged coverage (`great_work/service.py:1208`, `great_work/service.py:1992`).

### Objectives
1. Deliver layered press for mentorship lifecycle events (queue, activation, career progression, completion) and admin maintenance (pause/resume notifications, archive sync updates).
2. Ensure Gazette digests summarize pending scheduled drops so players anticipate upcoming stories.
3. Instrument the new layers in telemetry for cadence monitoring.

### Proposed Approach
- **Layer templates:**
  - Mentorship queue: immediate gossip from mentor, delayed scholar reaction, optional cohort commentary.
  - Activation: follow-up manifesto highlighting goals, delayed lab updates.
  - Completion: scheduled alumni spotlight + faction response.
  - Admin pause/resume: immediate bulletin + staged operational updates for players.
- **Scheduler integration:**
  - Extend `_apply_multi_press_layers` usage inside mentorship/admin handlers; add Gazette digest summary generator that describes the next scheduled follow-ups per event.
- **Telemetry hooks:**
  - Tag mentorship/admin layers for reporting; log queue depth via new telemetry events.

### Decision Points
1. **Cadence duration defaults:** ✅ Support dual presets—"flash" layers (0–90 minutes) for immediate follow-ups and "long-form" arcs that can stretch across multiple digests or days. Expose both via settings.
2. **Digest summary format:** ✅ Deliver upcoming highlights through an opt-in channel (e.g., `#gazette-upcoming`) so players choose whether to receive cadence teasers.

### Implementation Plan
1. Expand `MultiPressGenerator` with helpers for mentorship/admin layers and configurable delay presets via settings.
2. Update `GameService` mentorship/admin flows to queue the new layers and emit digest summary metadata.
3. Modify Gazette digest composer to include upcoming highlights section, respecting pause state.
4. Add telemetry for scheduled layer counts and mentorship/admin queue depth to feed the dashboards.
5. Write tests covering new layering behaviour and digest summaries.

## Next Steps & Approvals

1. Document dashboard container configuration presets (port mappings, sample compose entry) for operators and include guidance on interpreting symposium scoring/debt widgets and reprisal thresholds.
2. Confirm naming conventions for the opt-in upcoming-highlights channel and integrate into onboarding docs.

## Narrative Arc Completion Plan

To close the remaining narrative gaps (sidecasts, defection epilogues, deep-prep sideways vignettes) we will ship the following data-driven structures and scheduling hooks:

### A. Sidecast Arcs
- **Data:** new `great_work/data/sidecast_arcs.yaml` describing archetype-specific sidecast beats with three phases: `debut`, `integration`, `spotlight`. Each phase defines fast gossip quotes, long-form briefs, optional mentorship prompts, and follow-up orders (e.g., `enqueue_order: mentorship_invite`).
- **Scheduling:** `_maybe_spawn_sidecast` seeds the new scholar as today, then queues a sidecast follow-up order (`followup:sidecast_debut`) that runs through the dispatcher. Subsequent phases trigger after mentorship acceptance or elapsed time, emitting layered press via `MultiPressGenerator.generate_sidecast_layers` with tone-pack support.
- **Mentorship hooks:** when a player mentors a sidecast scholar, the integration spotlight shifts to the mentor, queuing layered press that references the mentorship track and rewards the player with bespoke copy.

### B. Defection Epilogues
- **Data:** extend `great_work/data/defection_epilogues.yaml` mapping outcome (`return`, `rivalry`, `scorched_earth`) to tone, staged headlines, faction statements, and reconciliation mechanics (e.g., influence refunds, scars). Templates include optional admin alerts for high-integrity scholars.
- **Scheduling:** when a `defection_return` follow-up resolves, swap the generic gossip for a multi-press bundle: apology letter, faction briefing, commons reactions. If the scholar refuses reconciliation, queue a rivalry order that periodically triggers gossip until resolved.
- **Telemetry:** track epilogue outcomes via new system events so `/telemetry_report` records rates of successful returns versus rivalries.

### C. Deep-Prep Sideways Vignettes
- **Data:** new `great_work/data/sideways_vignettes.yaml` with entries keyed by expedition type + prep depth. Each defines narrative text, mechanical payload (faction shifts, opportunities, theory seeds), and optional chained follow-ups (e.g., conference, symposium topic, sidecast trigger).
- **Integration:** `ExpeditionResolver._generate_sideways_effects` selects vignette bundles, registers tags, and enqueues follow-up press orders that surface in digest highlights. Tone packs gain `sideways_vignette` seeds for each setting.

### D. Vignette Coverage & Tone Safety
- **Coverage target:** minimum of **three** vignettes per expedition type/depth combination (think tank shallow/standard/deep, field shallow/standard/deep, great project deep) so RNG draws different arcs across a campaign. Additional slots remain open for future expansions (e.g., symposium, great project standard) with the same structure.
- **Content guidelines:** each vignette entry must include a `headline`, `body`, and at least one gossip quote. Tag with thematic markers (`archives`, `industry`, `politics`) so digest highlights badge them appropriately.
- **Tone guardrails:**
  - Keep tone-pack entries for `sidecast_followup`, `defection_epilogue`, and `sideways_vignette` descriptive rather than prescriptive—avoid inflammatory language and call out moderation steps (e.g., “Flag rivalry flare-ups”).
  - When writing vignette copy, run it through the PG-13 filter, avoid references to real-world conflicts, and ensure reconciliation/rivalry beats do not encourage harassment.
  - Document new tone seeds in this file and run a manual spot-check whenever tone packs expand. Telemetry will flag any tone key missing from `press_tone_packs.yaml`.

### D. Dispatcher & Press Support
- Implement `MultiPressGenerator.generate_sidecast_layers` and `generate_defection_epilogues` helpers drawing from the new YAML assets so layered press reuses fast/long cadence settings.
- Add dispatcher order types `sidecast_debut`, `sidecast_spotlight`, `defection_epilogue`, and `sideways_vignette_followup`, all tracked via the existing telemetry/alert pathways.

With these structures in place we can populate the YAML libraries with the required copy and wire the service layer to deliver the staged narratives the HLD calls for.

With hosting, dashboard medium, and cadence cadence decisions set, we can proceed into implementation planning for Phase 3 polish.
