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

## 4. Archive Publishing

- The scheduler exports HTML to `web_archive/` each digest, syncs it into `web_archive_public/`, and uploads ZIP snapshots to the admin channel.
- To serve the archive publicly, run the `archive_server` container (nginx) and map the port.
- Retention defaults to 30 snapshots; adjust `GREAT_WORK_ARCHIVE_MAX_SNAPSHOTS` if you require more history.
- Refer to `docs/internal/ARCHIVE_OPERATIONS.md` for recovery steps and manual export instructions.

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
