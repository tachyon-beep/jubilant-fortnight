# Deployment & Configuration Guide

This guide outlines the configuration required to run The Great Work in production, including Discord channel routing, telemetry alerts, archive hosting, and optional LLM setup.

Terminology:

- Orders dispatcher — shared delayed-action queue backed by the `orders` table.
- Gazette scheduler — APScheduler jobs that run digests and weekly symposia.
- Narrative assets (YAML copy and tone packs) ship under CC BY 4.0; review `docs/NARRATIVE_LICENSE.md` before publishing new content to ensure attribution requirements are met.

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
GREAT_WORK_ALERT_MIN_ACTIVE_PLAYERS=3       # alert if fewer than 3 players issue commands in 24h
GREAT_WORK_ALERT_MIN_MANIFESTO_RATE=0.5     # alert if <50% of active players publish manifestos over 7d
GREAT_WORK_ALERT_MIN_ARCHIVE_LOOKUPS=1      # alert if the archive sees no lookups within 7d
GREAT_WORK_ALERT_MAX_SEASONAL_DEBT=25       # alert if seasonal commitments exceed 25 influence outstanding
# Optional outbound routing (leave blank to disable)
# GREAT_WORK_ALERT_WEBHOOK_URLS=https://ops.example/webhook,https://oncall.example/webhook
# GREAT_WORK_ALERT_WEBHOOK_URL=
# GREAT_WORK_ALERT_COOLDOWN_SECONDS=300
# GREAT_WORK_ALERT_MUTED_EVENTS=
# GREAT_WORK_ALERT_EMAIL_HOST=
# GREAT_WORK_ALERT_EMAIL_PORT=587
# GREAT_WORK_ALERT_EMAIL_USERNAME=
# GREAT_WORK_ALERT_EMAIL_PASSWORD=
# GREAT_WORK_ALERT_EMAIL_FROM=
# GREAT_WORK_ALERT_EMAIL_TO=
# GREAT_WORK_ALERT_EMAIL_STARTTLS=true

# Narrative Tone (optional)
GREAT_WORK_PRESS_SETTING=post_cyberpunk_collapse  # or high_fantasy, renaissance_europe_1400s

# LLM Configuration (optional)
LLM_API_BASE=http://localhost:5000/v1
LLM_API_KEY=not-needed-for-local
LLM_MODEL_NAME=local-model
LLM_TEMPERATURE=0.8
LLM_MAX_TOKENS=500
LLM_TIMEOUT=30
LLM_RETRY_ATTEMPTS=3
LLM_RETRY_SCHEDULE=1,3,10,30                # seconds between retries
LLM_USE_FALLBACK=true
LLM_SAFETY_ENABLED=true
LLM_BATCH_SIZE=10
LLM_MODE=           # set to "mock" to bypass calls in dev

# Guardian Sidecar Moderation
GREAT_WORK_GUARDIAN_MODE=sidecar             # sidecar (HTTP RPC) or local
GREAT_WORK_GUARDIAN_URL=http://localhost:8085/score   # Only in sidecar mode
# GREAT_WORK_GUARDIAN_LOCAL_PATH=./models/guardian    # Path to weights when mode=local
GREAT_WORK_GUARDIAN_CATEGORIES=HAP,sexual,violence,self-harm,illicit
GREAT_WORK_MODERATION_STRICT=true            # If true, pause the game when the sidecar is offline
GREAT_WORK_MODERATION_PREFILTER_ONLY=false  # Force regex-only moderation (for development)

# Archive Publishing (optional overrides)
GREAT_WORK_ARCHIVE_BASE_URL=/archive                # Adjust when hosting under a prefix
GREAT_WORK_ARCHIVE_PAGES_DIR=/opt/great-work-pages  # Local clone of the gh-pages branch
GREAT_WORK_ARCHIVE_PAGES_SUBDIR=archive             # Subdirectory inside the pages repo
GREAT_WORK_ARCHIVE_PAGES_NOJEKYLL=true              # Emit .nojekyll marker on publish
GREAT_WORK_ARCHIVE_PAGES_ENABLED=true               # Toggle GitHub Pages mirroring
GREAT_WORK_ARCHIVE_MAX_STORAGE_MB=512               # Alert threshold for local snapshots

# Embeddings & Qdrant (optional)
# Enable semantic search and knowledge indexing
GREAT_WORK_QDRANT_INDEXING=false
# EMBEDDING_MODEL defaults to sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
# Qdrant service URL used by tools/CLIs (override via --url as needed)
# QDRANT_URL=http://localhost:6333
```

Informational slash commands (`/status`, `/symposium_status`, `/symposium_proposals`, `/symposium_backlog`, `/wager`, `/seasonal_commitments`, `/faction_projects`, `/gazette`, `/export_log`) mirror their output to the first available channel in this list: `GREAT_WORK_CHANNEL_TABLE_TALK`, `GREAT_WORK_CHANNEL_GAZETTE`, `GREAT_WORK_CHANNEL_UPCOMING`, `GREAT_WORK_CHANNEL_ORDERS`. Configure at least one of these so transparency requirements are met.

Adjust the alert numbers to match your cadence; for example, if you expect long digests, raise `GREAT_WORK_ALERT_MAX_DIGEST_MS`. When the queue builds up, the orders dispatcher metrics and admin notifications help the operator intervene.

## 2. Running with Docker Compose

The repository ships with a `docker-compose.yml` that includes:

- `qdrant`: vector DB for embeddings and semantic search (optional)
- `archive_server`: nginx serving `web_archive_public/`
- `telemetry_dashboard` (optional): FastAPI dashboard for telemetry visuals

Start supporting services:

```bash
docker compose up -d archive_server telemetry_dashboard qdrant
```

Mount the `web_archive_public/` volume so the scheduler can sync exports (default path works out of the box). The nginx container listens on port 8080 by default; expose it or reverse proxy it as needed and open firewall access, e.g. `sudo ufw allow 8081/tcp` if you remap ports.

## 3. Telemetry Dashboard

The optional `telemetry-dashboard` service reads `var/telemetry/telemetry.db` and exposes charts for command usage, layered press cadence, queue depth, digest health, and KPI trend lines (active players, manifestos, archive lookups). It bundles Chart.js via CDN, so allow outbound HTTPS for that asset or vendor the bundle if you need an air-gapped deployment.

- Default port: `8081`
- Environment requirements: same `.env` file (or a subset with `TELEMETRY_DB_PATH`)
- Access locally at `http://localhost:8081`

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
- **Seasonal debt** – When outstanding seasonal commitments exceed the alert ceiling, review current pledges,
  encourage manual repayments, or lower the base cost/reprisal penalties via the new calibration helper before
  reprisals cascade.
- **Nickname adoption** – Low nickname activity suggests the roster isn't resonating. If the adoption rate falls
  below the alert floor, seed nicknames via Gazette stories or prompt players directly.
- **Press shares** – Monitor how often players broadcast Gazette copy. When shares dip below the floor, spotlight
  notable releases manually or share automated highlights to rekindle engagement.

### Orders Dispatcher Moderation

- List pending work with `/gw_admin list_orders` (filter by order type and status). Results show the order
  id, actor, subject, and payload preview.
- Additional filters include `actor_id`, `subject_id`, and `older_than_hours`; toggles `include_payload=true` and `as_file=true`
  expose full JSON payloads or attach the output as a text file when Discord message limits would truncate it.
- Cancel items with `/gw_admin cancel_order order_id:<id> [reason:<text>]`. The game logs the cancellation,
  emits telemetry, and notifies the admin channel. Cancelled orders no longer execute during the digest tick.
- For bulk reviews, run `python -m great_work.tools.manage_orders summary --json` to stream order counts or
  `python -m great_work.tools.manage_orders followups migrate` to migrate any legacy `followups` rows after a dry run.

Update the environment variables to tune when alerts trigger, and capture any operator-specific playbook additions in your internal notes.
Right-size the KPI thresholds for your cohort—drop `GREAT_WORK_ALERT_MIN_ACTIVE_PLAYERS` to 2–3 for tiny playtests or temporarily mute manifesto/archive checks while onboarding new groups.

### KPI Calibration Workflow

1. Export recent telemetry (or run the server with `var/telemetry/telemetry.db` mounted) and execute:

   ```bash
   python -m great_work.tools.recommend_kpi_thresholds --db var/telemetry/telemetry.db
   ```

   The script samples command usage, manifesto adoption, nickname adoption, archive lookups, and press shares, then prints recommended environment variables (scaled from recent activity). Use the `--engagement-days`, `--manifesto-days`, and `--archive-days` flags to widen or narrow the analysis window.
2. Copy the suggested values into your deployment environment (`GREAT_WORK_ALERT_MIN_ACTIVE_PLAYERS`, `GREAT_WORK_ALERT_MIN_MANIFESTO_RATE`, `GREAT_WORK_ALERT_MIN_NICKNAME_RATE`, `GREAT_WORK_ALERT_MIN_ARCHIVE_LOOKUPS`, `GREAT_WORK_ALERT_MIN_PRESS_SHARES`) and redeploy or reload the bot.
3. Configure multiple alert targets (e.g., Discord plus on-call) by setting `GREAT_WORK_ALERT_WEBHOOK_URLS` with a comma-separated list. The router fans out to each endpoint while keeping the legacy `GREAT_WORK_ALERT_WEBHOOK_URL` for single-target setups.
4. Send a smoke test once the environment variables are live (`python -m great_work.tools.simple_alert_webhook` locally or a curl POST) to confirm alerts land in both channels.

### Seasonal Commitment Tuning

1. Analyse recent seasonal debt with:

   ```bash
   python -m great_work.tools.recommend_seasonal_settings --db var/telemetry/telemetry.db --days 30
   ```

   Review the average/median outstanding debt and the suggested knobs (base cost, reprisal threshold, `GREAT_WORK_ALERT_MAX_SEASONAL_DEBT`).
2. Update `settings.yaml` (or environment overrides) with the recommended values so seasonal pledges clear on schedule without generating runaway debt.
3. Adjust `GREAT_WORK_ALERT_MAX_SEASONAL_DEBT` to match the suggested ceiling so the new health check triggers before reprisals spiral.

### Calibration Snapshot Automation

1. Enable recurring snapshots by setting `GREAT_WORK_CALIBRATION_SNAPSHOTS=true` (or specifying `GREAT_WORK_CALIBRATION_SNAPSHOT_DIR` for the output directory). Optional knobs: `GREAT_WORK_CALIBRATION_SNAPSHOT_KEEP` (retention, default 12) and `GREAT_WORK_CALIBRATION_SNAPSHOT_DETAILS=false` for aggregate-only payloads.
2. The Gazette scheduler now writes timestamped JSON files plus `latest.json` after each digest. Mirror the directory to long-term storage if you need historical tuning records.
3. Run `/gw_admin calibration_snapshot` or `python -m great_work.tools.export_calibration_snapshot --stdout` to generate a snapshot on demand; both honour the same environment configuration and return summaries covering seasonal debt, faction investment totals, endowments, and pending orders.
4. The telemetry dashboard exposes the most recent snapshot at `/api/calibration_snapshot` and surfaces key totals at the top of the UI.
5. Use the dashboard’s dispatcher filter form (or call `/api/orders?event=poll&min_pending=3`) to pull JSON/CSV samples during live triage.

Use `python -m great_work.tools.generate_sample_telemetry` to populate a fresh `var/telemetry/telemetry.db` with deterministic sample data when rehearsing the workflow before live players arrive.

### Guardian Sidecar Operations

1. **Provision weights:** run `python -m great_work.tools.download_guardian_model --target ./models/guardian` on the host (requires `huggingface_hub`).
2. **Sidecar service:** deploy the guardian container (`docker compose up guardian-sidecar`) or start the systemd unit; the service must expose a `/score` endpoint that accepts JSON payloads `{ "category": "HAP", "text": "..." }`.
3. **Health checks:** confirm `/health` returns `ok` and that `/gw_admin moderation_recent` shows steady Guardian latency in `/telemetry_report`.
4. **Incident response:** if `moderation_sidecar_offline` fires, restart the sidecar and decide whether to set `GREAT_WORK_MODERATION_STRICT=false` temporarily or pause the game via `/gw_admin pause_game reason:"guardian offline"`. After recovery, audit overrides with `/gw_admin moderation_overrides`.
5. **Manual probes:** send a sample to the sidecar directly, e.g.

   ```bash
   curl -sS -X POST "$GREAT_WORK_GUARDIAN_URL" \
     -H 'Content-Type: application/json' \
     -d '{"text": "sample text", "categories": ["HAP"]}' | jq .
   ```

### Preflight Smoke Check

Before launching a new environment run:

```bash
python -m great_work.tools.deployment_smoke
```

The command reports missing tokens, channel routing gaps, Guardian misconfiguration, and alert routing coverage. Resolve any **error** rows before starting the bot; **warning** rows highlight optional but recommended settings (e.g., public channel mirroring or alert webhooks).

## 4. Archive Publishing

- The scheduler exports HTML to `web_archive/` each digest, syncs it into `web_archive_public/`, and uploads ZIP snapshots to the admin channel.
- To serve the archive publicly, run the `archive_server` container (nginx) and map the port.
- Retention defaults to 30 snapshots; adjust `GREAT_WORK_ARCHIVE_MAX_SNAPSHOTS` if you require more history.
- For a managed host, point `GREAT_WORK_ARCHIVE_PAGES_DIR` at a local clone of your GitHub Pages branch (for example, `gh-pages`). The scheduler mirrors each digest export into `<repo>/<GREAT_WORK_ARCHIVE_PAGES_SUBDIR>` (default `archive/`), drops a `.nojekyll` marker, and emits telemetry on success/failure. Commit and push the branch to publish.
- Set `GREAT_WORK_ARCHIVE_BASE_URL` to match the public path (e.g., `/my-org/great-work/archive`) so generated permalinks resolve correctly on Pages.
- Snapshots are now monitored via `GREAT_WORK_ARCHIVE_MAX_STORAGE_MB`; when the total ZIP size exceeds the limit the scheduler notifies the admin channel and records telemetry.
- Configure `GREAT_WORK_ALERT_WEBHOOK_URL` and optional email settings (`GREAT_WORK_ALERT_EMAIL_*`) so guardrail hits reach your operations channels even when no one is watching Discord; leave them blank to rely on console logs only. For local smoke tests you can run `python -m great_work.tools.simple_alert_webhook --port 8085` and target `http://localhost:8085` to inspect payloads.
  For recovery steps, GitHub Pages workflow details, and manual export instructions, keep an internal runbook aligned with your hosting setup.
- Optional: enable the `Publish Archive to Pages` GitHub Action to auto-commit/push updates. Seed the `gh-pages` branch once, then run the workflow (push-trigger or manual dispatch) whenever `web_archive_public/` contains fresh exports.
- `settings.yaml` also exposes `archive_publishing.github_pages` defaults so deployments can enable/disable Pages mirroring without environment overrides.
- Configure `GREAT_WORK_ALERT_WEBHOOK_URL` plus cooldown/muting (and optional email) variables to forward guardrail hits to the operations webhook of your choice (Discord/Slack/etc.). When unset, alerts log to the bot console only.

## 5. Local LLM Persona Stack

Set `LLM_MODE=mock` in development to bypass live LLM calls. For production use a local or hosted OpenAI-compatible endpoint and configure:

```env
LLM_API_BASE=http://your-llm-host:port/v1
LLM_API_KEY=your_key
LLM_MODEL_NAME=your_model
```

The game pauses automatically if the LLM fails repeatedly; monitor admin notifications and `/telemetry_report` for pause/resume events.

## 6. Moderation Sidecar

- Download Granite Guardian weights with `python -m great_work.tools.download_guardian_model --target ./models/guardian` (defaults to `ibm-granite/granite-guardian-3.2-3b-a800m`; requires `pip install huggingface_hub`). Authentication follows the standard Hugging Face token flow; pass `--token` explicitly or rely on cached credentials.
- Run the moderation sidecar (Ollama, container, or custom service) beside the bot and expose an HTTP endpoint. See `docs/archive/SAFETY_PLAN.md` for architecture and operational guidance.
- Leave the script unused if you prefer an alternate moderation provider—the repository ships without any large binaries by default.
- Optional environment knobs:

  ```env
  GREAT_WORK_GUARDIAN_MODE=sidecar      # or local
  GREAT_WORK_GUARDIAN_URL=http://localhost:8085/score
  GREAT_WORK_GUARDIAN_ENABLED=true
  GREAT_WORK_GUARDIAN_LOCAL_PATH=./models/guardian   # when using local mode
  GREAT_WORK_GUARDIAN_CATEGORIES=HAP,sexual,violence,self-harm,illicit
  ```

## 7. Firewall & Networking Checklist

- Open Discord outbound access (HTTPS).
- Expose only the ports you need (e.g., `archive_server` 8080, telemetry dashboard 8081) and restrict via firewall rules (`ufw`, security groups, etc.).
- Secure `.env`/secrets (`DISCORD_TOKEN`, `LLM_API_KEY`).

With these settings and services in place, operators can launch the bot, review telemetry, and serve the archive with minimal manual intervention.
