# Archive Snapshot Operations

This note captures the operational workflow for the Gazette archive pipeline. The scheduler now exports the full static archive on every digest tick, syncs the output into the container-served site, and ships a timestamped ZIP snapshot to the admin channel. Operators can use the procedures below to monitor retention, recover artefacts, or perform manual exports when needed.

## Snapshot Locations

- Export build directory: `web_archive/`
- Container-served directory (nginx): `web_archive_public/`
- Snapshot directory: `web_archive/snapshots/`
- Snapshot filename format: `web_archive_YYYYMMDD_HHMMSS.zip`
- Discord admin channel receives the same ZIP via automated upload (see scheduler logs for confirmation).
- The archive container reads from `web_archive_public/`; confirm the volume is mounted when running `docker-compose up archive_server`. By default the container listens on port 8080; expose it (for example with `docker-compose` port mapping) and open firewall access via `sudo ufw allow 8081/tcp` if you proxy externally.

## Retention & Cleanup

1. Keep the most recent **30** snapshots on disk; older files can be pruned to save space.
   ```bash
   find web_archive/snapshots -name 'web_archive_*.zip' -mtime +30 -delete
   ```
2. If storage pressure becomes acute, archive older ZIPs to long-term storage before deletion.
3. Ensure at least the latest snapshot remains available locally when performing cleanups.

## Manual Export

Run the export command to generate a fresh archive on demand. This triggers telemetry, updates `web_archive_public/`, and will be picked up by the scheduler on the next cycle.
```bash
source .venv/bin/activate
python -m great_work.discord_bot export_web_archive
```
The ZIP will appear in `web_archive/snapshots/` and a message will post to the admin channel.

## Recovery Procedure

1. Identify the desired snapshot either from disk (`web_archive/snapshots/`) or by downloading it from the admin channel history.
2. Unzip to a temporary directory:
   ```bash
   unzip web_archive/snapshots/web_archive_YYYYMMDD_HHMMSS.zip -d /tmp/web_archive_restore
   ```
3. To restore the container-served site, delete the existing `web_archive_public/` contents and copy the restored files into the directory (the nginx container will serve the updated assets automatically).
4. If replacing the live archive, replace contents of `web_archive/` with the restored files and run the export command to regenerate derived metadata (the sync step will republish to `web_archive_public/`).

## Monitoring & Telemetry

- Scheduler logs (via Discord bot logs) include lines like `Archive published to container directory` and `Web archive snapshot published to admin channel` with the full path.
- Telemetry records `archive_published_container` and `web_archive_export` system events to track frequency and success; review `/telemetry_report` or the bundled dashboard for recent activity.

## Best Practices

- Verify the admin channel post after each digest to confirm uploads are succeeding and check `archive_server` container logs if the public site fails to update.
- When switching to external hosting (e.g., S3), disable `GREAT_WORK_ARCHIVE_PUBLISH_DIR` and configure the appropriate publisher adapter.
- Keep bot credentials secure; snapshot uploads rely on the configured admin channel ID, and the nginx container exposes static files on port 8080 by default.
- Default alert thresholds (`GREAT_WORK_ALERT_MAX_DIGEST_MS=5000`, `GREAT_WORK_ALERT_MAX_QUEUE=12`,
  `GREAT_WORK_ALERT_MIN_RELEASES=1`, `GREAT_WORK_ALERT_MAX_LLM_LATENCY_MS=4000`,
  `GREAT_WORK_ALERT_LLM_FAILURE_RATE=0.25`, `GREAT_WORK_ALERT_MAX_ORDER_PENDING=6`,
  `GREAT_WORK_ALERT_MAX_ORDER_AGE_HOURS=8`) keep the scheduler noisy only when runtimes spike, the
  scheduled queue backs up, or digests publish nothing—adjust in production if your cadence differs.
