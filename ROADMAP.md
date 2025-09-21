# The Great Work Roadmap

> Status: Tracking post-1.0 initiatives. Use this document to coordinate future gameplay, telemetry, and player-facing enhancements once the 1.0 release candidate has shipped.

## Summary Table

| Theme | Goal | Status |
| --- | --- | --- |
| Gameplay & Narrative Enhancements | Expand scholar drama (dynasties, conspiracies, betting markets, cascades). | Concept backlog |
| Telemetry Cohort Comparison | Baseline vs. current KPI overlays, cohort preservation, export tooling. | Future enhancement |
| Player Telemetry Portal | OAuth-protected player dossier with influence graphs and press highlights. | Future enhancement |

## 1. Gameplay & Narrative Enhancements (Concept Backlog)

These ideas are distilled from the former `post_1_0/GAME_ENHANCEMENTS.md`. They focus on deepening long-term drama, cascading failure, and social storytelling. Highlights include:

- **Academic Dynasties** – Scholars age, retire, and raise academic offspring who inherit traits and grudges. Alliances can be arranged through academic “marriages”.
- **Secret Societies & Conspiracies** – Hidden cabals leave breadcrumbs across expedition finds and press copy. Exposing conspiracies grants major reputation swings.
- **Catastrophic Cascades** – Spectacular failures trigger rescue missions, department shutdowns, and multi-digest cliffhangers.
- **Scholar Romance & Affairs** – Relationship entanglements influence mentorship efficacy and defection odds.
- **Betting Markets & Insider Scandals** – Influence markets allow wagers on theories, spawning bubbles and crash headlines.
- Additional concepts: mental health & sabbaticals, academic trials, cults/zealotry, cross-campaign artifacts, prophetic dream mechanics.

> **Next Steps:** Prioritise one or two pillars that align with live ops feedback post-1.0. Each concept should be broken into incremental deliverables (data schema, press templates, UI hooks) before entering the implementation queue.

## 2. Telemetry Cohort Comparisons

Objective: allow operators to benchmark current playtests against historical cohorts (e.g., “v0.9 pilot vs current week”). Key capabilities envisioned in the retired `TELEMETRY_COHORT_COMPARISONS.md`:

1. **Baseline Selection** – Store named cohorts with start/end bounds. Provide APIs to retrieve daily KPI aggregates (average, median, percentile).
2. **Overlay Visualisations** – Update the telemetry dashboard with comparison bands (baseline percentiles) alongside current KPI trend lines.
3. **Delta Summaries** – Surface quick comparisons (“Active players +12% vs baseline”) for status reports.
4. **Snapshot Export** – Generate markdown/PNG exports for weekly ops updates.

> **Technical Notes:** Requires extending `TelemetryCollector` with cohort-aware queries, new FastAPI endpoints (`/api/kpi_cohort`, `/api/kpi_compare`), and caching to keep dashboards responsive.

## 3. Player Telemetry Portal

Goal: offer players a self-service portal (OAuth via Discord) to review their history. Derived from `USER_TELEMETRY.md`. Proposed features:

- **Recent Timeline** – Display the player’s recent commands, nicknames, press shares, and results.
- **Influence & Reputation Graphs** – Visualise five-faction influence, reputation deltas, seasonal pledges.
- **Press Collections** – Highlight Gazette entries mentioning the player or their scholars.
- **Scholar & Nickname Panels** – Show current mentorships, scholar loyalty, and nickname adoption.
- **Telemetry Snapshots** – Reuse telemetry metrics to chart command mix, manifesto contributions, press-sharing streaks.

> **Architecture Sketch:** Extend the existing FastAPI dashboard with player-scoped endpoints (`/api/player/<discord_id>/…`) and a lightweight SPA/HTMX frontend. Enforce strict auth, rate limits, and opt-in data exports.

## 4. Archive Log

The original `docs/post_1_0/` folder has been consolidated here for ease of discovery. Historical drafts can be referenced in version control if detailed prose or brainstorming notes are required.

| Former File | Replacement |
| --- | --- |
| `docs/post_1_0/GAME_ENHANCEMENTS.md` | §1 above |
| `docs/post_1_0/TELEMETRY_COHORT_COMPARISONS.md` | §2 above |
| `docs/post_1_0/USER_TELEMETRY.md` | §3 above |

Going forward, add new roadmap items directly to this document and keep the table of contents aligned with strategic focus areas.

