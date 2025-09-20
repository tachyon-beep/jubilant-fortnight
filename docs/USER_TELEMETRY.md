# Player Telemetry Portal (Post-1.0 Concept)

> Status: Future enhancement, not in scope for the 1.0 release.

## Goal

Give individual players a self-service view into their own activity so they can audit their decisions, track influence flows, and celebrate highlights without needing operator intervention. The portal should feel like a personalized dossier layered on top of the existing telemetry infrastructure.

## Core Capabilities

- **Authentication by Discord ID:** reuse the existing OAuth flow (as in the admin dashboard) so players can sign in with the same Discord identity the bot associates with their moves.
- **Recent Timeline:** list the player’s most recent actions (commands, nicknames, press shares, investments) with timestamps and the resulting press or outcomes.
- **Influence & Reputation Graph:** chart their five-vector influence history, reputation shifts, and seasonal commitments.
- **Press Collections:** highlight Gazette stories that mention the player or their scholars, with quick links to view/share.
- **Nickname & Scholar Panel:** show the nicknames they have recorded and the scholars they currently mentor or influence.
- **Telemetry Snapshots:** pull the per-player metrics the collector already stores (`track_command`, `track_game_progression`) and render them as lightweight charts (command frequency, manifesto involvement, press shares).

## Architecture Sketch

1. **API Layer:** extend the existing telemetry FastAPI app or add a sibling service that exposes per-player endpoints (`/api/player/<discord_id>/events`, `/api/player/<discord_id>/metrics`). Limit them to authenticated requests signed by the player’s Discord token.
2. **Frontend:** a simple single-page app (React/Vue or plain HTMX) that:
   - fetches event + metric data after login
   - renders charts (reuse Chart.js already adopted for operator dashboards)
   - provides filters (last 7/30 days, specific factions, expedition vs symposium)
3. **Data Source:** leverage the telemetry database (`TelemetryCollector`) plus the primary SQLite databases for richer event context (press headlines, scholar bios). Precompute some aggregates (cumulative influence, pledge history) via background cron or on-demand caching.

## Privacy & Safety Considerations

- Only surface data attributable to the signing player—no other player metrics or cross-player comparisons.
- Respect Discord channel privacy: omit messages delivered to private channels unless they originated from the player.
- Provide an export option (`Download My Data`) to satisfy basic data portability expectations.

## Implementation Steps (future)

1. Prototype read-only API endpoints that return the same telemetry payloads we currently embed in `/telemetry_report`, scoped to a single player.
2. Build the frontend with OAuth + session storage using the existing dashboard container, but behind a separate route (`/player` vs `/admin`).
3. Add new telemetry helpers (`TelemetryCollector.get_player_history`, `get_player_press_shares`) to avoid duplicating SQL per request.
4. Iterate on UX: start with tables + charts, then add narrative flourishes (e.g., “Highlights of the week”, “Most shared press”).
5. Harden with rate limits + alerting so the player portal cannot flood the telemetry database.

## Open Questions

- Should the player portal integrate into Discord via ephemeral embeds, or remain web-only?
- How much of the archive should a player be able to filter/annotate from their portal (e.g., tagging favorite stories)?
- Would players value opt-in telemetry sharing (e.g., sharing a “season recap” card) for social proof?

Tracking details and prioritization will follow once Phase 3 post-launch work begins. This document lives alongside `GAME_ENHANCEMENTS.md` as aspirational scope.
