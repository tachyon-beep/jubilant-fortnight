Screenshots for PRs and docs live here.

Recommended captures for the Sprint 2 PR:

- telemetry_dashboard.png — Dashboard home showing Health Summary and Dispatcher Backlog.
- gazette_digest.png — Discord Gazette post with layered press (headlines + body snippets).

How to capture:

1) Telemetry dashboard
   - Start with Docker Compose: `docker compose up -d telemetry_dashboard`
   - Open `http://localhost:8081`
   - Select a recent window with activity; screenshot Health Summary and Dispatcher Backlog

2) Gazette digest
   - Seed a local DB: `make seed DB=great_work.db`
   - Run the bot: `make run` (or call the service directly in tests)
   - Trigger `/resolve_expeditions` or wait for a scheduled digest
   - Screenshot the Gazette output in Discord

