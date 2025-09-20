# KPI Cohort Comparison Dashboard (Post-1.0 Concept)

> Status: Future enhancement. Nice-to-have after the 1.0 telemetry guardrails ship.

## Motivation

Operators have asked for a quick way to benchmark new playtests against prior runs (e.g., “Is this week’s symposium engagement higher than last month’s?”). While the current dashboard shows absolute KPI history, cohort overlays would make deviations obvious and help product evaluate tuning changes.

## Desired Capabilities

1. **Baseline Selection:** Allow ops to choose a historical window (specific date range or named cohort) to serve as the comparison baseline.
2. **Overlay Charts:** Plot current KPI lines (active players, manifestos, archive lookups, nicknames, press shares) alongside the baseline average/percentile bands.
3. **Delta Summaries:** Provide quick stats (e.g., “Active players +12% vs baseline”, “Press shares −30%”) for the chosen window.
4. **Snapshot Export:** Generate a Markdown/PNG summary that can be dropped into weekly status reports.

## Technical Sketch

- **Data Layer:**
  - Extend `TelemetryCollector` with helper queries that aggregate KPIs by arbitrary date range (average, median, standard deviation).
  - Persist named cohorts in a new table (`kpi_cohorts`) containing start/end bounds and human-readable labels.
- **API/Backend:**
  - Add `/api/kpi_cohort?start=...&end=...` and `/api/kpi_compare?baseline=cohort_id&current=range` endpoints that return both raw daily points and aggregate summaries.
- **Frontend:**
  - Update the dashboard to include a “Cohort Comparison” section with dropdowns for baseline and current windows.
  - Render dual-line visualizations or a fill-range (baseline percentile band + current line) using Chart.js.

## Privacy & Scope

No player-specific data is exposed beyond aggregate telemetry that already appears in `/telemetry_report`. We remain within the operator-only footprint; the player portal (`USER_TELEMETRY.md`) covers individual access separately.

## Implementation Steps (future)

1. Draft SQL helpers and unit tests for arbitrary window aggregation.
2. Ship API endpoints with query validation and simple caching (e.g., 10-minute in-memory cache per cohort).
3. Integrate Chart.js overlay visualizations plus a delta summary table.
4. Add a “Save cohort” UI so ops can bookmark notable playtests (pilot, v0.9, v1.0) for quick comparisons.
5. Document the workflow in `docs/deployment.md` once live.

This file tracks the enhancement until telemetry feature work resumes post-1.0.
