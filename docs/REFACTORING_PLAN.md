# Refactoring Plan

## Objectives

- Reduce god-modules, clarify boundaries, and improve testability.
- Preserve behavior and keep tests green while iterating.
- Enable future features with a modular, layered structure.

## Scope (Initial)

- Focus on `great_work/` core: `service.py`, `discord_bot.py`, `state.py`, `telemetry.py`, `multi_press.py`, `scheduler.py`, `web_archive.py`.
- Non-goals: Feature work, database schema changes, or protocol changes to Discord commands (unless required for decoupling).

## Hotspots (size/complexity)

- `service.py` (~8.1k LOC, longest fn ~329 lines)
- `discord_bot.py` (~3.3k LOC, longest fn ~165 lines)
- `state.py` (~3.0k LOC, 130 defs)
- `telemetry.py` (~2.8k LOC, longest fn ~239 lines)
- `multi_press.py` (~2.0k LOC)

## Target Architecture (packages)

- `great_work/domain/` — Pure domain models, policies, value objects.
- `great_work/services/` — Application services (game, orders, narrative, economy).
- `great_work/adapters/` — Discord, persistence, LLM, vector DB, web/archive.
- `great_work/infrastructure/` — Repos, DB/session, configuration, schedulers.
- `great_work/telemetry/` — Collectors, KPIs, exporters, schemas.

## Phased Migration Plan

1) Scaffold + Shims
   - Add subpackages above; keep existing imports working via thin re-exports/compat.
2) Split `service.py`
   - Move orchestration into `services/game.py`; extract orders/economy/narrative flows into small services.
3) Extract Discord adapter
   - `adapters/discord/{bot.py, handlers.py, builders.py}`; keep event wiring thin.
4) Repository layer
   - Replace direct calls in `state.py` with repositories per aggregate; centralize transactions.
5) Telemetry module split
   - Separate KPI functions, collectors, and exporters; keep functions pure and testable.
6) Scheduler and jobs
   - Keep `scheduler.py` minimal; move job logic near owning services.
7) Press/narrative pipeline
   - Break `multi_press.py` into template loading, prompt build, render, post-process; expose `press.generate(...)`.
8) Web archive
   - Separate data assembly from file I/O; template small HTML/Markdown where helpful.

## Quality Gates

- Tests: `make test` (target ≥80% coverage new/changed code).
- Lint/format: `make lint` and `ruff format .`.
- No behavior changes without tests; use feature flags for risky switches.
- Small PRs per phase; keep `chore/delint-refactor-cruft` regularly synced with `main`.

## Rollout & Backout

- Each phase merges behind shims; remove shims only after callers updated and tests stable.
- Backout by reverting the phase PR; shims prevent breakage.

## Useful Commands

- Setup: `make venv && make install`
- Run tests: `make test`
- Lint: `make lint`
- Bot (local): `make run` (loads `.env`)
