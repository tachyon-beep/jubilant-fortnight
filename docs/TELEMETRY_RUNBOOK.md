# Telemetry & Alerting Runbook

## Purpose

This runbook explains how to interpret the `/telemetry_report`, respond to alert thresholds, and tune the guardrails that protect live ops. Operators should consult this document whenever the health summary shows ⚠️/🛑 or when preparing patch notes after major tuning passes.

## Key Commands & Dashboards

- `/telemetry_report` – one-shot health snapshot inside Discord (admin only).
- `ops/telemetry-dashboard` – historical charts for digests, queue depth, and command usage (run via `make telemetry-dashboard`).
- `sqlite3 telemetry.db` – direct access if you need to export raw metrics.

## Health Checks & Thresholds

| Metric | Default Threshold (env var) | Description | Response |
| --- | --- | --- | --- |
| Digest runtime | 5000 ms (`GREAT_WORK_ALERT_MAX_DIGEST_MS`) | Maximum duration of the last 24h digests | If alert, inspect LLM latency + queued press; consider pausing digest automation. |
| Digest release floor | ≥ 1 item (`GREAT_WORK_ALERT_MIN_RELEASES`) | Lowest item count published in 24h | Alert usually means Gazette starved – check press queue + LLM. |
| Press queue depth | 12 items (`GREAT_WORK_ALERT_MAX_QUEUE`) | Max scheduled press backlog | Investigate stuck follow-ups or manual edits; consider cancelling obsolete orders. |
| LLM latency | 4000 ms (`GREAT_WORK_ALERT_MAX_LLM_LATENCY_MS`) | Weighted average call latency | Check `/gw_admin pause_game` triggers, failover LLM, or reduce batch sizes. |
| LLM failure rate | 20 % (`GREAT_WORK_ALERT_LLM_FAILURE_RATE`) | Error ratio by call volume | Inspect `errors_24h` section for root cause; pause high-cost features until clear. |
| Dispatcher pending | 6 orders (`GREAT_WORK_ALERT_MAX_ORDER_PENDING`) | Highest pending count per order type | Cancel or fast-track the offending order type. |
| Dispatcher staleness | 8 h (`GREAT_WORK_ALERT_MAX_ORDER_AGE_HOURS`) | Oldest order age | If repeated, escalate to narrative ops for manual resolution. |
| Symposium debt | 30 influence (`GREAT_WORK_ALERT_MAX_SYMPOSIUM_DEBT`) | Sum of outstanding symposium debt | Alert indicates players falling behind – consider rescheduling pledges or lowering penalties. |
| Symposium reprisals | 3 per player (`GREAT_WORK_ALERT_MAX_SYMPOSIUM_REPRISALS`) | Highest reprisal count in 24 h | Reach out to the affected player; consider waiving upcoming penalties. |
| Investment concentration | 60 % share (`GREAT_WORK_ALERT_INVESTMENT_SHARE`) | Share of investments attributed to a single player | If alert, encourage rival factions or seed new long-tail sinks. |
| Archive snapshot usage | 512 MB (`GREAT_WORK_ARCHIVE_MAX_STORAGE_MB`) | Total size of ZIP snapshots kept on disk | If alert, prune old snapshots or move them to long-term storage before the disk fills. |

### Adjusting Thresholds

Set environment variables in the Discord bot environment and restart the service. Example for a tighter queue limit:

```bash
export GREAT_WORK_ALERT_MAX_QUEUE=8
```

All thresholds are evaluated as warnings at 75 % of the configured value before escalating to alerts.

### Alert Routing

Set `GREAT_WORK_ALERT_WEBHOOK_URL` to forward guardrail breaches to an external destination (Discord webhook, Slack incoming URL, PagerDuty relay, etc.). Alerts are throttled via `GREAT_WORK_ALERT_COOLDOWN_SECONDS` (default 300 s) and you can silence noisy signals temporarily with `GREAT_WORK_ALERT_MUTED_EVENTS` (comma-separated event names such as `alert_health_digest_runtime`). When no webhook is configured the alerts fall back to the bot’s logs so operators still see the notifications. If email is easier to deploy, populate the `GREAT_WORK_ALERT_EMAIL_*` variables—alerts will be mirrored via SMTP in addition to any webhook configured.

Events emitted through `TelemetryCollector.track_system_event` using the `alert_` prefix—including dispatcher backlog warnings, health-check failures, and symposium reprisal spikes—automatically route through the webhook once their cooldown expires.

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

If investments concentrate on one player, consider introducing temporary incentives (e.g., discounted programs) for other factions.

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
- The telemetry dashboard now exposes dispatcher backlog filters and CSV export—use the controls above the table to select the order type, time window, and download the latest events for moderation review.

## Quick Reference

| Action | Command |
| --- | --- |
| Force telemetry flush | `/telemetry_report` (auto flush) |
| View dispatcher backlog | `/gw_admin list_orders` |
| Cancel stuck order | `/gw_admin cancel_order order_id:<id>` |
| Pause game due to alerts | `/gw_admin pause_game reason:"telemetry alert"` |
| Resume after fix | `/gw_admin resume_game` |
| Export dispatcher backlog CSV | Dashboard → Dispatcher Backlog → Export |

Keep this runbook with the other ops docs so every on-call operator understands the guardrails and remediation steps.
