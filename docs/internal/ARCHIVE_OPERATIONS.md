# Archive Snapshot Operations

This note captures the operational workflow for the Gazette archive pipeline. The scheduler now exports the full static archive on every digest tick and ships a timestamped ZIP snapshot to the admin channel. Operators can use the procedures below to monitor retention, recover artefacts, or perform manual exports when needed.

## Snapshot Locations

- Live archive directory: `web_archive/`
- Snapshot directory: `web_archive/snapshots/`
- Snapshot filename format: `web_archive_YYYYMMDD_HHMMSS.zip`
- Discord admin channel receives the same ZIP via automated upload (see scheduler logs for confirmation).

## Retention & Cleanup

1. Keep the most recent **30** snapshots on disk; older files can be pruned to save space.
   ```bash
   find web_archive/snapshots -name 'web_archive_*.zip' -mtime +30 -delete
   ```
2. If storage pressure becomes acute, archive older ZIPs to long-term storage before deletion.
3. Ensure at least the latest snapshot remains available locally when performing cleanups.

## Manual Export

Run the export command to generate a fresh archive on demand. This triggers telemetry and will be picked up by the scheduler on the next cycle.
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
3. Serve or copy the restored directory to the hosting location (e.g., S3 bucket, static web server).
4. If replacing the live archive, replace contents of `web_archive/` with the restored files and run the export command to regenerate derived metadata.

## Monitoring & Telemetry

- Scheduler logs (via Discord bot logs) include lines like `Web archive snapshot published to admin channel` with the full path.
- Telemetry records `web_archive_export` system events to track frequency and success; review `/telemetry_report` for recent export activity.

## Best Practices

- Verify the admin channel post after each digest to confirm uploads are succeeding.
- When rotating secrets or moving the archive host, update the operator docs in `docs/implementation_plan.md` to match the new workflow.
- Keep bot credentials secure; snapshot uploads rely on the configured admin channel ID.
