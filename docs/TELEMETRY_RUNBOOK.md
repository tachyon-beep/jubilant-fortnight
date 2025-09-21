# Telemetry & Alerting Runbook

## Purpose

This runbook explains how to interpret the `/telemetry_report`, respond to alert thresholds, and tune the guardrails that protect live ops. Operators should consult this document whenever the health summary shows ⚠️/🛑 or when preparing patch notes after major tuning passes.

## Key Commands & Dashboards

- `/telemetry_report` – one-shot health snapshot inside Discord (admin only).
- `ops/telemetry-dashboard` – historical charts for digests, queue depth, and command usage (run via `make telemetry-dashboard`).
- `sqlite3 telemetry.db` – direct access if you need to export raw metrics.
- `/gw_admin calibration_snapshot` – capture a calibration snapshot JSON and archive it in the admin channel.
- `python -m great_work.tools.export_calibration_snapshot` – export the same snapshot on disk (supports summary-only mode and retention pruning).
- `python -m great_work.tools.generate_sample_telemetry` – seed synthetic telemetry for dry runs before live data arrives.
- `python -m great_work.tools.recommend_kpi_thresholds --apply` – compute KPI guardrail suggestions from recent telemetry and persist them to `telemetry.db`; add `--output telemetry_exports/kpi_thresholds.json` for an audit trail.
- `python -m great_work.tools.export_product_metrics` – dump current KPIs, historical trends, and cohort breakdowns to `telemetry_exports/` for offline dashboards or quarterly reviews.
- `python -m great_work.tools.manage_orders` – summarise dispatcher orders and run follow-up migrations with optional JSON output.
- `python -m great_work.tools.calibrate_moderation` – inspect Guardian category/severity counts for tuning and override review.

## Calibration Snapshots & Tuning Workflow

- **Scheduler integration:** enable automated snapshots by setting `GREAT_WORK_CALIBRATION_SNAPSHOTS=true` or pointing `GREAT_WORK_CALIBRATION_SNAPSHOT_DIR` at a writable directory (defaults to `calibration_snapshots/`). The scheduler honours `GREAT_WORK_CALIBRATION_SNAPSHOT_KEEP` (default 12) and `GREAT_WORK_CALIBRATION_SNAPSHOT_DETAILS` (`false` to emit aggregate-only files).
- **On-demand export:** run `/gw_admin calibration_snapshot` or `python -m great_work.tools.export_calibration_snapshot --stdout` to capture the latest totals before a tuning review. Both commands respect the same environment configuration and pin a `latest.json` alongside timestamped files.
- **Dashboard visibility:** the telemetry dashboard now surfaces the latest snapshot summary and exposes the raw JSON at `/api/calibration_snapshot`.
- **Live-data follow-up:** once 1.0 telemetry is available, analyse seasonal debt, investment totals, and archival endowments from the snapshot to adjust defaults in `settings.yaml`. Use `python -m great_work.tools.recommend_seasonal_settings` to fold the findings back into configuration and update this runbook with the chosen baselines.

## Dispatcher Backlog Operations

- `/gw_admin list_orders` now supports `actor_id`, `subject_id`, and `older_than_hours` filters, plus `include_payload` and `as_file` toggles for detailed reviews.
- Cancel stale work with `/gw_admin cancel_order order_id:<id> [reason:<text>]`; cancellations emit telemetry and admin notifications.
- The telemetry dashboard hosts a dispatcher filter form that proxies `/api/orders` and `/api/orders.csv`, accepting additional query parameters (`event`, `min_pending`, `min_age_hours`).
- Use `python -m great_work.tools.manage_orders summary --json` for job-friendly snapshots or `python -m great_work.tools.manage_orders followups migrate` to convert legacy `followups` rows into dispatcher orders with a structured report.

## Narrative Surface Health

- Digest telemetry now records the press mix per cycle; review `/telemetry_report` → "Long-tail Economy" and "Press Cadence" sections to ensure varied templates keep firing.
- Moderation metrics surface in `/telemetry_report` under "Moderation (24h)"—watch for spikes in specific categories and run `python -m great_work.tools.calibrate_moderation --json` when retuning Guardian thresholds.

## Health Checks & Thresholds

| Metric | Default Threshold (env var) | Description | Response |
| --- | --- | --- | --- |
| Digest runtime | 5000 ms (`GREAT_WORK_ALERT_MAX_DIGEST_MS`) | Maximum duration of the last 24h digests | If alert, inspect LLM latency + queued press; consider pausing digest automation. |
| Digest release floor | ≥ 1 item (`GREAT_WORK_ALERT_MIN_RELEASES`) | Lowest item count published in 24h | Alert usually means Gazette starved – check press queue + LLM. |
| Press queue depth | 12 items (`GREAT_WORK_ALERT_MAX_QUEUE`) | Max scheduled press backlog | Investigate stuck follow-ups or manual edits; consider cancelling obsolete orders. |
| LLM latency | 4000 ms (`GREAT_WORK_ALERT_MAX_LLM_LATENCY_MS`) | Weighted average call latency | Check `/gw_admin pause_game` triggers, failover LLM, or reduce batch sizes. |
| LLM failure rate | 20 % (`GREAT_WORK_ALERT_LLM_FAILURE_RATE`) | Error ratio by call volume | Inspect `errors_24h` section for root cause; pause high-cost features until clear. |
| Orders dispatcher pending | 6 orders (`GREAT_WORK_ALERT_MAX_ORDER_PENDING`) | Highest pending count per order type | Cancel or fast-track the offending order type. |
| Orders dispatcher staleness | 8 h (`GREAT_WORK_ALERT_MAX_ORDER_AGE_HOURS`) | Oldest order age | If repeated, escalate to narrative ops for manual resolution. |
| Symposium debt | 30 influence (`GREAT_WORK_ALERT_MAX_SYMPOSIUM_DEBT`) | Sum of outstanding symposium debt | Alert indicates players falling behind – consider rescheduling pledges or lowering penalties. |
| Symposium reprisals | 3 per player (`GREAT_WORK_ALERT_MAX_SYMPOSIUM_REPRISALS`) | Highest reprisal count in 24 h | Reach out to the affected player; consider waiving upcoming penalties. |
| Investment concentration | 60 % share (`GREAT_WORK_ALERT_INVESTMENT_SHARE`) | Share of investments attributed to a single player | If alert, encourage rival factions or seed new long-tail sinks. |
| Archive snapshot usage | 512 MB (`GREAT_WORK_ARCHIVE_MAX_STORAGE_MB`) | Total size of ZIP snapshots kept on disk | If alert, prune old snapshots or move them to long-term storage before the disk fills. |
| Seasonal commitments | same as reprisal threshold (`GREAT_WORK_SEASONAL_COMMITMENT_REPRISAL_THRESHOLD`) | Outstanding upkeep owed before reprisal | Alert fires when debt approaches the reprisal threshold—nudge the player or adjust the pact before penalties land. |

### Adjusting Thresholds

Set environment variables in the Discord bot environment and restart the service. Example for a tighter queue limit:

```bash
export GREAT_WORK_ALERT_MAX_QUEUE=8
```

All thresholds are evaluated as warnings at 75 % of the configured value before escalating to alerts.

Canonical KPI targets live in the `kpi_targets` table inside `telemetry.db`. Use either the calibration CLI (`python -m great_work.tools.recommend_kpi_thresholds --apply`) or a short Python shell to upsert new values:

```python
from great_work.telemetry import TelemetryCollector
collector = TelemetryCollector("telemetry.db")
collector.set_kpi_target("active_players", target=6, warning=4, notes="Beta baseline")
```

Targets appear in `/telemetry_report`, drive the dashboard’s KPI table, and automatically override the matching alert thresholds (`active_players`, `manifesto_adoption`, `archive_usage`, `nickname_rate`, `press_shares`). Update both the database entry and any environment defaults so deployment manifests stay in sync with the tuned guardrails.

### Alert Routing

Set `GREAT_WORK_ALERT_WEBHOOK_URLS` with a comma-separated list to fan alerts out to multiple destinations (Discord, Slack, PagerDuty, etc.), and optionally keep `GREAT_WORK_ALERT_WEBHOOK_URL` for legacy single-channel setups. Alerts are throttled via `GREAT_WORK_ALERT_COOLDOWN_SECONDS` (default 300 s) and you can silence noisy signals temporarily with `GREAT_WORK_ALERT_MUTED_EVENTS` (comma-separated event names such as `alert_health_digest_runtime`). When no webhook is configured the alerts fall back to the bot’s logs so operators still see the notifications. If email is easier to deploy, populate the `GREAT_WORK_ALERT_EMAIL_*` variables—alerts will be mirrored via SMTP alongside the webhook fan-out.

Events emitted through `TelemetryCollector.track_system_event` using the `alert_` prefix—including orders dispatcher backlog warnings, health-check failures, and symposium reprisal spikes—automatically route through the webhook once their cooldown expires.

For local testing or demos run the bundled webhook receiver:

```bash
python -m great_work.tools.simple_alert_webhook --port 8085
```

Then point `GREAT_WORK_ALERT_WEBHOOK_URL` at `http://localhost:8085` to see alert payloads logged to the console.

## Economy & Long-Tail Signals

The telemetry report now includes:

- **Investments:** total influence invested over 24 h, top investors, and faction distribution. Use this to gauge whether sponsorship loops are active.
- **Archive endowments:** amount donated, symposium debt repaid, and total reputation bonuses awarded.
- **Symposium debt:** per-player debt with timestamps to monitor escalation windows.
- **Seasonal commitments:** per-player upkeep debt, days remaining, and reprisal threshold context. Alerts labeled `alert_commitment_overdue_*` fire when a player nears reprisal—coordinate with ops before penalties stack.

If investments concentrate on one player, consider introducing temporary incentives (e.g., discounted programs) for other factions.

## Engagement Cohorts & Symposium Participation

- `/telemetry_report` and the dashboard now list new vs returning player cohorts over the past seven days, including command volumes and top participants. Use these to validate onboarding/retention experiments and spot shifts in command mix.
- Symposium participation tables summarise command usage across `/symposium_vote`, `/symposium_status`, `/symposium_backlog`, and proposal commands. Investigate sudden drops (cohort share trending <25 %) before weekly digests to keep deliberations lively.
- Canonical KPI targets surface in the dashboard alongside each metric; update them via `TelemetryCollector.set_kpi_target` when product commits new engagement goals.

## Symposium Monitoring Workflow

1. Check "Symposium Signals" in `/telemetry_report`.
2. If debt exceeds threshold, ping the affected players and consider adding a catch-up grant.
3. For repeated reprisals, verify pledge settings in `settings.yaml` and adjust `reprisal_threshold`/`penalty` if the cadence is too aggressive.
4. Document follow-up actions in the ops log.

## Incident Response Checklist

1. Capture the relevant `/telemetry_report` output.
2. Identify which health checks tripped and gather supporting metrics (LLM, queue, economy).
3. Apply mitigations (pause digests, cancel orders, issue manual refunds) and note them in the ops channel.
4. After mitigation, re-run `/telemetry_report` to confirm recovery.
5. File an issue if configuration or code changes are needed.

## Data Retention

- Telemetry samples are retained for 30 days by default (see `TelemetryCollector.cleanup_old_data`).
- Run `python -m great_work.telemetry --prune` (or call `cleanup_old_data`) monthly to keep the DB compact.

## Archive Publishing Signals

- `archive_published_container` and `archive_published_github_pages` confirm each digest successfully deployed both the local nginx volume and the GitHub Pages repository. Investigate the scheduler logs if either event goes missing.
- `archive_publish_pages_failed` indicates the mirror step hit an exception (usually permissions or an uninitialised Pages directory); check the admin channel alert and repair the working tree.
- `archive_snapshot_usage` tracks rolling snapshot disk usage. When `archive_snapshot_usage_exceeded` fires, prune `web_archive/snapshots/` or offload older ZIPs before repeated digests fail.
- Review the Git working tree under `GREAT_WORK_ARCHIVE_PAGES_DIR` after a failure; partially synced content should be committed/pushed only after validation.
- The telemetry dashboard now exposes orders dispatcher backlog filters and CSV export—use the controls above the table to select the order type, time window, and download the latest events for moderation review.

## Quick Reference

| Action | Command |
| --- | --- |
| Force telemetry flush | `/telemetry_report` (auto flush) |
| View orders dispatcher backlog | `/gw_admin list_orders` |
| Cancel stuck order | `/gw_admin cancel_order order_id:<id>` |
| Pause game due to alerts | `/gw_admin pause_game reason:"telemetry alert"` |
| Resume after fix | `/gw_admin resume_game` |
| Export orders dispatcher backlog CSV | Dashboard → Dispatcher Backlog → Export |

Keep this runbook with the other ops docs so every on-call operator understands the guardrails and remediation steps.
