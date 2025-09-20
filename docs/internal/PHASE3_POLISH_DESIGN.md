# Phase 3 Polish Design Brief

## Purpose & Scope

Phase 3 focuses on operational polish: actionable telemetry, resilient archive publishing, and richer multi-layer press cadence. This brief captures the target outcomes, proposed approaches, and open decisions so implementation can proceed without ambiguity. It drills into three workstreams that remain after the latest telemetry/dispatcher audit and flags where stakeholder input is needed before coding.

## 1. Telemetry Dashboards & Success Metrics

### Current State
- All slash commands flow through `track_command`, emitting command usage with player, guild, channel, duration, and success tags (`great_work/telemetry_decorator.py:12`).
- LLM activity, system pause/resume events, and player-state snapshots are recorded in `telemetry.db` and surfaced via `/telemetry_report` (`great_work/discord_bot.py:786`, `great_work/telemetry.py:520`).
- Requirements still call for layered-press counts, engagement funnels, and explicit success criteria tracking (`docs/requirements_evaluation.md:157`).

### Objectives
1. Provide on-demand dashboards (Discord command + optional HTML summary) covering:
   - Layered press production and release cadence (by type, scheduled vs immediate).
   - Engagement metrics: unique players per digest, symposium participation, table-talk volume.
   - Health signals: digest duration, LLM latency distribution, pause frequency.
2. Define success metrics aligned with product goals (e.g., % public vs ephemeral replies, avg time from press schedule to release).
3. Establish alert thresholds for pause duration, command error spikes, and archive export failures.

### Proposed Approach
- **Schema additions:**
  - Add a `metrics_summary` view or derived table for layered press counts (ingest from `press_scheduled` events and scheduled queue releases).
  - Record digest runtime via a `track_performance` call wrapping `advance_digest` and `resolve_pending_expeditions`.
- **Reporting surfaces:**
  - Extend `/telemetry_report` with new sections (layered press, engagement, digest health) and paginate when output exceeds Discord limits.
  - Provide a `make telemetry-report` CLI option writing JSON for external dashboarding.
- **Alerting:**
  - Implement configurable thresholds in settings (e.g., `telemetry.alerts.pause_minutes`, `telemetry.alerts.error_rate`). When breached, enqueue admin notifications and log system events.

### Decision Points
1. **Dashboard medium:** Is a richer external dashboard (Grafana/Metabase) in scope, or do we remain Discord + JSON? _Recommendation_: begin with Discord/JSON; revisit after first pilot.
2. **Success metric targets:** Need product input on target ranges (e.g., acceptable pause duration, desired engagement numbers) before hard-coding alerts.

### Implementation Plan
1. Instrument digest runtimes and layered press metrics (order queue depth, scheduled release counts) in telemetry.
2. Update `TelemetryCollector.generate_report()` to compute the new aggregates.
3. Expand `/telemetry_report` formatting; add optional `--format json` CLI helper.
4. Introduce alert evaluation during digest ticks and command execution; send admin notifications when thresholds trip.
5. Document the workflow in `docs/implementation_plan.md` and operator guides.

## 2. Archive Automation & Hosting

### Current State
- Gazette scheduler exports the static archive every digest and uploads ZIP snapshots to the admin channel (`great_work/scheduler.py:20`, `docs/internal/ARCHIVE_OPERATIONS.md`).
- Hosting remains manual; snapshots accumulate locally and in Discord without automated rotation (`docs/gap_analysis.md:41`).

### Objectives
1. Publish the archive to a persistent host (S3 bucket, GitHub Pages, or similar) after each digest.
2. Implement retention policies for local and remote snapshots (e.g., keep last 30, prune older).
3. Provide a one-command operator workflow, with failure telemetry and admin alerts when publishing stalls.

### Proposed Approach
- **Hosting target (recommended):** Amazon S3 + CloudFront or an equivalent static host; alternative is Git-based deployment to GitHub Pages.
- **Automation flow:**
  1. After archive export, run a deployment hook (Python subprocess or dedicated worker) to sync `web_archive/` to the host (e.g., `aws s3 sync`).
  2. Record deployment metadata (commit hash, digest timestamp) in telemetry via `track_system_event`.
  3. Zip snapshots remain for disaster recovery; prune older than retention window.
- **Configuration:**
  - Extend settings with `archive.hosting` block (provider, credentials/env vars, retention days).
  - Add optional dry-run mode for local testing.
- **Monitoring:**
  - Emit telemetry on deployment duration/success.
  - Notify admin channel if publishing fails, including error summary and retry guidance.

### Decision Points
1. **Hosting provider choice:** Confirm preferred target (S3 vs. GitHub Pages vs. self-hosted). _Default_: S3 due to existing CLI tooling.
2. **Credential management:** Determine how operators will supply credentials (env vars, config file, secrets manager).

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
1. **Cadence duration defaults:** Recommend 30/60/120-minute staggering; confirm tolerance for longer arcs.
2. **Digest summary format:** Decide whether to append a “Coming soon” section to Gazette posts or provide a separate command.

### Implementation Plan
1. Expand `MultiPressGenerator` with helpers for mentorship/admin layers and configurable delay presets via settings.
2. Update `GameService` mentorship/admin flows to queue the new layers and emit digest summary metadata.
3. Modify Gazette digest composer to include upcoming highlights section, respecting pause state.
4. Add telemetry for scheduled layer counts and mentorship/admin queue depth to feed the dashboards.
5. Write tests covering new layering behaviour and digest summaries.

## Next Steps & Approvals

1. Confirm hosting provider and credential strategy for archive automation (decision owner: ops/product).
2. Align on telemetry dashboard medium and success-metric thresholds (decision owner: product/design).
3. Approve mentorship/admin cadence defaults and digest summary presentation (decision owner: narrative design).

Once the above decisions are locked, we can proceed with implementation tasks per the updated plan.
