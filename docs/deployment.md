# Deployment & Configuration Guide

This guide outlines the configuration required to run The Great Work in production, including Discord channel routing, telemetry alerts, archive hosting, and optional LLM setup.

## 1. Environment Variables

Create a `.env` (or use your secrets manager) with the following keys:

```env
# Discord Bot
DISCORD_TOKEN=your_bot_token
DISCORD_APP_ID=your_application_id
GREAT_WORK_CHANNEL_ORDERS=channel_id_for_orders
GREAT_WORK_CHANNEL_GAZETTE=channel_id_for_digest_posts
GREAT_WORK_CHANNEL_TABLE_TALK=channel_id_for_table_talk
GREAT_WORK_CHANNEL_ADMIN=channel_id_for_admin_notifications
GREAT_WORK_CHANNEL_UPCOMING=channel_id_for_optional_upcoming_highlights

# Telemetry & Alerts (tune per deployment)
GREAT_WORK_ALERT_MAX_DIGEST_MS=5000          # alert if digest exceeds 5s
GREAT_WORK_ALERT_MAX_QUEUE=12               # alert if scheduled press backlog exceeds 12 items
GREAT_WORK_ALERT_MIN_RELEASES=1             # alert if a digest emits fewer than 1 release
GREAT_WORK_ALERT_MAX_LLM_LATENCY_MS=4000    # alert if average LLM latency exceeds 4s
GREAT_WORK_ALERT_LLM_FAILURE_RATE=0.25      # alert if LLM failures exceed 25%
GREAT_WORK_ALERT_MAX_ORDER_PENDING=6        # alert if dispatcher backlog exceeds 6 orders
GREAT_WORK_ALERT_MAX_ORDER_AGE_HOURS=8      # alert if any pending order ages past 8h

# Narrative Tone (optional)
GREAT_WORK_PRESS_SETTING=post_cyberpunk_collapse  # or high_fantasy, renaissance_europe_1400s

# LLM Configuration (optional)
LLM_API_BASE=http://localhost:5000/v1
LLM_API_KEY=not-needed-for-local
LLM_MODEL=local-model
LLM_TIMEOUT=30
LLM_RETRY_ATTEMPTS=3
LLM_RETRY_SCHEDULE=1,3,10,30                # seconds between retries
LLM_USE_FALLBACK=true

# Archive Publishing (optional overrides)
GREAT_WORK_ARCHIVE_BASE_URL=/archive                # Adjust when hosting under a prefix
GREAT_WORK_ARCHIVE_PAGES_DIR=/opt/great-work-pages  # Local clone of the gh-pages branch
GREAT_WORK_ARCHIVE_PAGES_SUBDIR=archive             # Subdirectory inside the pages repo
GREAT_WORK_ARCHIVE_PAGES_NOJEKYLL=true              # Emit .nojekyll marker on publish
GREAT_WORK_ARCHIVE_PAGES_ENABLED=true               # Toggle GitHub Pages mirroring
GREAT_WORK_ARCHIVE_MAX_STORAGE_MB=512               # Alert threshold for local snapshots
```

Adjust the alert numbers to match your cadence; for example, if you expect long digests, raise `GREAT_WORK_ALERT_MAX_DIGEST_MS`. When the queue builds up, the scheduler records depth measurements and admin notifications help the operator intervene.

## 2. Running with Docker Compose

The repository ships with a `docker-compose.yml` that includes:

- `bot`: the Discord bot service
- `archive_server`: nginx serving `web_archive_public/`
- `telemetry-dashboard` (optional): FastAPI dashboard for telemetry visuals

Start everything:

```bash
docker compose up -d bot archive_server telemetry-dashboard
```

Mount the `web_archive_public/` volume so the scheduler can sync exports (default path works out of the box). The nginx container listens on port 8080 by default; expose it or reverse proxy it as needed and open firewall access, e.g. `sudo ufw allow 8081/tcp` if you remap ports.

## 3. Telemetry Dashboard

The optional `telemetry-dashboard` service reads `telemetry.db` and exposes charts for command usage, layered press cadence, queue depth, and digest health.

- Default port: `8082`
- Environment requirements: same `.env` file (or a subset with `TELEMETRY_DB_PATH`)
- Access locally at `http://localhost:8082`

If you forgo the dashboard, `/telemetry_report` in Discord prints queue depth, digest stats, and alert thresholds.

### Telemetry Runbook

The `/telemetry_report` command now opens with a **Health Summary**, mapping key metrics to the thresholds above. Icons show the current status (`✅` OK, `⚠️` approaching threshold, `🛑` exceeded). When a metric fires:

- **Digest runtime** – When runtime crosses the limit, review recent digests, LLM queues, and
  archive publishing. Investigate long-running narrative generation and consider pausing scheduled
  digests if latency persists.
- **Digest release floor** – A warning that a digest published fewer than the expected minimum
  (default `1`). Check `service.pending_press_count()` and ensure scheduled follow-ups are being
  generated; confirm the scheduler is not paused.
- **Press queue depth** – Highlights the deepest backlog sampled in the last 24 hours. If it exceeds
  the queue threshold, triage outstanding follow-ups, prune stale orders, or increase digest frequency.
- **LLM latency** – Average LLM latency above the threshold usually indicates a saturated
  model endpoint. Check the LLM service health, retry budget, and consider switching to fallback
  mode.
- **LLM failure rate** – When failures pass the allowed rate, review admin notifications for
  pause events, inspect the LLM logs, and manually pause the game if necessary.
- **Dispatcher backlog** – When pending orders rise above the limit, prioritise resolving them during
  the next digest and look for blocked mentorships/conferences. An admin notification is posted when this
  threshold trips.
- **Order staleness** – If any pending order ages past the staleness threshold, investigate why it has
  not resolved (e.g., missing data, paused scheduler) and consider canceling/re-queuing. Admins receive a
  reminder once the stale age threshold is crossed.

### Dispatcher Moderation

- List pending work with `/gw_admin list_orders` (filter by order type and status). Results show the order
  id, actor, subject, and payload preview.
- Cancel items with `/gw_admin cancel_order order_id:<id> [reason:<text>]`. The game logs the cancellation,
  emits telemetry, and notifies the admin channel. Cancelled orders no longer execute during the digest tick.

Update the environment variables to tune when alerts trigger, and capture any operator-specific playbook additions in your internal notes.

## 4. Archive Publishing

- The scheduler exports HTML to `web_archive/` each digest, syncs it into `web_archive_public/`, and uploads ZIP snapshots to the admin channel.
- To serve the archive publicly, run the `archive_server` container (nginx) and map the port.
- Retention defaults to 30 snapshots; adjust `GREAT_WORK_ARCHIVE_MAX_SNAPSHOTS` if you require more history.
- For a managed host, point `GREAT_WORK_ARCHIVE_PAGES_DIR` at a local clone of your GitHub Pages branch (for example, `gh-pages`). The scheduler mirrors each digest export into `<repo>/<GREAT_WORK_ARCHIVE_PAGES_SUBDIR>` (default `archive/`), drops a `.nojekyll` marker, and emits telemetry on success/failure. Commit and push the branch to publish.
- Set `GREAT_WORK_ARCHIVE_BASE_URL` to match the public path (e.g., `/my-org/great-work/archive`) so generated permalinks resolve correctly on Pages.
- Snapshots are now monitored via `GREAT_WORK_ARCHIVE_MAX_STORAGE_MB`; when the total ZIP size exceeds the limit the scheduler notifies the admin channel and records telemetry.
- Refer to `docs/internal/ARCHIVE_OPERATIONS.md` for recovery steps, GitHub Pages workflow details, and manual export instructions.
- Optional: enable the `Publish Archive to Pages` GitHub Action to auto-commit/push updates. Seed the `gh-pages` branch once, then run the workflow (push-trigger or manual dispatch) whenever `web_archive_public/` contains fresh exports.
- `settings.yaml` also exposes `archive_publishing.github_pages` defaults so deployments can enable/disable Pages mirroring without environment overrides.

## 5. Local LLM Persona Stack

Set `LLM_MODE=mock` in development to bypass live LLM calls. For production use a local or hosted OpenAI-compatible endpoint and configure:

```env
LLM_API_BASE=http://your-llm-host:port/v1
LLM_API_KEY=your_key
LLM_MODEL=your_model
```

The game pauses automatically if the LLM fails repeatedly; monitor admin notifications and `/telemetry_report` for pause/resume events.

## 6. Firewall & Networking Checklist

- Open Discord outbound access (HTTPS).
- Expose only the ports you need (e.g., `archive_server` 8080, telemetry dashboard 8082) and restrict via firewall rules (`ufw`, security groups, etc.).
- Secure `.env`/secrets (`DISCORD_TOKEN`, `LLM_API_KEY`).

With these settings and services in place, operators can launch the bot, review telemetry, and serve the archive with minimal manual intervention.
