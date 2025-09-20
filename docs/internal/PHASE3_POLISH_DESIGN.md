# Phase 3 Polish Design Brief

## Purpose & Scope

Phase 3 focuses on operational polish: actionable telemetry, resilient archive publishing, and richer multi-layer press cadence. This brief captures the target outcomes, proposed approaches, and open decisions so implementation can proceed without ambiguity. It drills into three workstreams that remain after the latest telemetry/dispatcher audit and flags where stakeholder input is needed before coding.

## 1. Telemetry Dashboards & Success Metrics

### Current State
- All slash commands flow through `track_command`, emitting command usage with player, guild, channel, duration, and success tags (`great_work/telemetry_decorator.py:12`).
- LLM activity, system pause/resume events, queue-depth sampling, and player-state snapshots are recorded in `telemetry.db` and surfaced via `/telemetry_report` (`great_work/discord_bot.py:786`, `great_work/telemetry.py:520`).
- Requirements still call for engagement funnels and explicit success criteria tracking (`docs/requirements_evaluation.md:157`).

### Objectives
1. Provide on-demand dashboards (Discord command + bundled HTML dashboard) covering:
   - Layered press production and release cadence (by type, scheduled vs immediate).
   - Engagement metrics: unique players per digest, symposium participation, table-talk volume.
   - Health signals: digest duration, LLM latency distribution, pause frequency.
2. Define success metrics aligned with product goals (e.g., % public vs ephemeral replies, avg time from press schedule to release).
3. Establish alert thresholds for pause duration, command error spikes, and archive export failures.

### Proposed Approach
- **Schema additions:**
  - Queue depth snapshots are emitted directly via `track_queue_depth`; continue enriching layered press counts (ingest from `press_scheduled` events and scheduled queue releases).
  - Record digest runtime via a `track_performance` call wrapping `advance_digest` and `resolve_pending_expeditions`.
- **Reporting surfaces:**
  - Extend `/telemetry_report` with new sections (layered press, engagement, digest health) and paginate when output exceeds Discord limits.
  - Ship a lightweight FastAPI/Jinja dashboard inside the ops container to visualise historical metrics directly from `telemetry.db`.
- **Alerting:**
  - Configurable thresholds exposed via environment variables (`GREAT_WORK_ALERT_MAX_DIGEST_MS`, `GREAT_WORK_ALERT_MAX_QUEUE`, `GREAT_WORK_ALERT_MIN_RELEASES`). When breached, enqueue admin notifications and log system events.
- **Operator notes:**
  - `/telemetry_report` now prints queue depth averages/maxima alongside the active thresholds, giving moderators a quick read on backlog health.
  - Queue depth snapshots are sampled when upcoming highlights are generated (default horizon 48h); adjust horizon via `GREAT_WORK_CHANNEL_UPCOMING` settings if cadence changes.

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

1. Finalise success-metric thresholds (pause duration, engagement targets) for alerting defaults.
2. Document dashboard container configuration presets (port mappings, sample compose entry) for operators.
3. Confirm naming conventions for the opt-in upcoming-highlights channel and integrate into onboarding docs.

With hosting, dashboard medium, and cadence cadence decisions set, we can proceed into implementation planning for Phase 3 polish.
